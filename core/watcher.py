# watcher background update workers and the 30-minute scheduler.


import os
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from config import SIDECAR_FILENAME
from core.ai_engine import AIEngine
from core import memory
from core.sidecar import (
    get_file_entry,
    get_folder_entry,
    get_file_history,
    load_sidecar,
    needs_update,
    update_file_desc,
    update_folder_desc,
)


# Per-folder update worker

class UpdateWorker(QThread):
    progress      = Signal(str)          # status text for status bar
    file_done     = Signal(str, str)     # (folder_path, filename)
    folder_done   = Signal(str)          # folder_path
    error         = Signal(str)
    finished_work = Signal()

    def __init__(
        self,
        folder_path: str,
        ai: AIEngine,
        force: bool = False,
        staleness_days: int = 4,
        generate_narrative: bool = True,
    ):
        super().__init__()
        self.folder_path       = folder_path
        self.ai                = ai
        self.force             = force
        self.staleness_days    = staleness_days
        self.generate_narrative = generate_narrative
        self._running          = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            folder = self.folder_path
            self.progress.emit(f"Scanning {Path(folder).name} …")

            try:
                all_items = os.listdir(folder)
            except PermissionError:
                self.error.emit("Permission denied")
                return

            files = [
                fn for fn in all_items
                if os.path.isfile(os.path.join(folder, fn))
                and fn != SIDECAR_FILENAME
                and not fn.startswith(".")
            ]

            sidecar = load_sidecar(folder)
            updated = {}   # fname → desc dict (for folder summary)

            for fn in files:
                if not self._running:
                    break

                fp = os.path.join(folder, fn)

                if not self.force and not needs_update(folder, fn, self.staleness_days):
                    # Reuse stored description for the folder summary
                    stored = sidecar.get("files", {}).get(fn, {})
                    if stored:
                        updated[fn] = stored
                    continue

                self.progress.emit(f"Analysing {fn} …")
                result = self.ai.describe_file(fp)

                #  Narrative generation
                narrative = ""
                if self.generate_narrative and self.ai.is_configured():
                    self.progress.emit(f"Building narrative for {fn} …")
                    try:
                        old_narrative = memory.get_narrative(fp)
                        old_history   = memory.get_history(fp, limit=3)
                        # Also try sidecar history if memory is empty (first run)
                        if not old_history:
                            old_history = get_file_history(folder, fn)

                        # Determine mode for word-count target
                        from core.ai_engine import extract_content
                        _, _, _, mode = extract_content(fp, self.ai.config)

                        narrative = self.ai.generate_narrative(
                            file_path     = fp,
                            old_narrative = old_narrative,
                            new_short     = result["short"],
                            new_long      = result["long"],
                            history       = old_history,
                            mode          = mode,
                        )
                    except Exception as ne:
                        print(f"[watcher] narrative error for {fn}: {ne}")

                # Persist to sidecar
                update_file_desc(
                    folder, fn,
                    result["short"], result["long"],
                    manual_lock        = False,
                    sensitive_detected = result.get("sensitive_detected", False),
                    sensitive_types    = result.get("sensitive_types", []),
                    tags               = result.get("tags", []),
                    narrative          = narrative,
                )

                # Persist to SQLite memory
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    size = 0
                try:
                    memory.add_history_entry(
                        fp, result["short"], result["long"], source="ai"
                    )
                    memory.index_file(
                        path            = fp,
                        folder          = folder,
                        name            = fn,
                        short_desc      = result["short"],
                        long_desc       = result["long"],
                        narrative       = narrative,
                        tags            = result.get("tags", []),
                        sensitive       = result.get("sensitive_detected", False),
                        manual_lock     = False,
                        last_updated    = "",   # sidecar just wrote real timestamp
                        file_size_bytes = size,
                    )
                except Exception as me:
                    print(f"[watcher] memory index error for {fn}: {me}")

                updated[fn] = {
                    "short_desc":        result["short"],
                    "long_desc":         result["long"],
                    "sensitive_detected": result.get("sensitive_detected", False),
                }
                self.file_done.emit(folder, fn)

            # Folder description 
            folder_entry = sidecar.get("folder", {})
            if not folder_entry.get("manual_lock", False) or self.force:
                self.progress.emit("Generating folder summary …")
                fresult = self.ai.describe_folder(folder, updated)
                update_folder_desc(
                    folder,
                    fresult["short"], fresult["long"],
                    sensitive_detected = fresult.get("sensitive_detected", False),
                    tags               = fresult.get("tags", []),
                )
                self.folder_done.emit(folder)

            self.progress.emit("Up to date")

        except Exception as e:
            self.error.emit(str(e))
        finally:
            memory.close_thread_connection()
            self.finished_work.emit()


#  Watcher manager

class FolderWatcher(QObject):
    """Holds a timer and spawns UpdateWorkers for watched folders."""

    update_started   = Signal(str)     # folder_path
    update_finished  = Signal(str)     # folder_path
    status_msg       = Signal(str)     # human-readable status
    file_refreshed   = Signal(str, str)  # (folder, filename)
    folder_refreshed = Signal(str)       # folder

    def __init__(
        self,
        ai: AIEngine,
        interval_minutes: int = 30,
        staleness_days: int = 4,
    ):
        super().__init__()
        self.ai              = ai
        self.staleness_days  = staleness_days
        self._watched:  set  = set()
        self._workers: dict[str, UpdateWorker] = {}

        # Ensure the SQLite memory DB is ready on startup
        try:
            memory.init_db()
        except Exception as e:
            print(f"[watcher] memory DB init error: {e}")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scheduled_run)
        self.set_interval(interval_minutes)

    # Public API

    def watch(self, folder_path: str):
        self._watched.add(folder_path)

    def unwatch(self, folder_path: str):
        self._watched.discard(folder_path)

    def trigger(self, folder_path: str, force: bool = False):
        """Start an immediate update for one folder (non-blocking)."""
        if folder_path in self._workers and self._workers[folder_path].isRunning():
            return

        cfg = self.ai.config
        gen_narrative = cfg.get("generate_narrative", True)

        w = UpdateWorker(
            folder_path,
            self.ai,
            force              = force,
            staleness_days     = self.staleness_days,
            generate_narrative = gen_narrative,
        )
        w.progress.connect(self.status_msg)
        w.file_done.connect(self.file_refreshed)
        w.folder_done.connect(self.folder_refreshed)
        w.error.connect(lambda e: self.status_msg.emit(f"Error: {e}"))
        w.finished_work.connect(lambda: self._worker_done(folder_path))
        self._workers[folder_path] = w
        self.update_started.emit(folder_path)
        w.start()

    def set_interval(self, minutes: int):
        self._timer.setInterval(max(1, minutes) * 60_000)
        if not self._timer.isActive():
            self._timer.start()

    def stop_all(self):
        self._timer.stop()
        for w in self._workers.values():
            w.stop()

    # Index a folder's existing sidecar into memory (fast catch-up)

    def index_folder(self, folder_path: str):
        """
        Bulk-index an already-described folder's sidecar into the SQLite memory
        without calling the AI.  Called when a folder is opened.
        """
        try:
            sidecar = load_sidecar(folder_path)
            memory.index_from_sidecar(folder_path, sidecar)
        except Exception as e:
            print(f"[watcher] index_folder error: {e}")

    # Internal

    def _scheduled_run(self):
        for folder in list(self._watched):
            self.trigger(folder, force=False)

    def _worker_done(self, folder_path: str):
        self.update_finished.emit(folder_path)
