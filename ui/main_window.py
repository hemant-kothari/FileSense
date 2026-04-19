"""
Main Window — FileSense file browser.

Layout:
  Toolbar: Settings | Open Folder | Home | Graph View | Refresh All | Export
  Content stack:
    [0] Main view  — 3-column splitter (folder tree | file list | right-panel-stack)
                     Right-panel stack: [0] desc panel  [1] settings  [2] edit desc
    [1] Graph view — horizontal mind-map
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QDir, QFileInfo, QModelIndex, QSize, Qt, QThread, Signal,
)
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QProgressBar, QSizePolicy, QSplitter, QStackedWidget,
    QStatusBar, QToolBar, QTreeView, QVBoxLayout, QWidget,
    QFileSystemModel,
)

from config import SIDECAR_FILENAME, load_config, save_config
from core.ai_engine import AIEngine
from core.sidecar import (
    export_shareable,
    get_file_entry,
    get_folder_entry,
    load_sidecar,
    set_manual_lock,
    update_file_desc,
    update_folder_desc,
)
from core.watcher import FolderWatcher
from ui.desc_panel import DescriptionPanel
from ui.dialogs import SettingsPanel, EditDescPanel
from ui.graph import MindMapWidget


# File list item

class FileItem(QListWidgetItem):
    def __init__(self, name: str, is_folder: bool, short_desc: str = "",
                 sensitive: bool = False, manual: bool = False):
        super().__init__()
        self.file_name  = name
        self.is_folder  = is_folder
        self.short_desc = short_desc
        self._render(sensitive, manual)

    def _render(self, sensitive: bool, manual: bool):
        icon  = "📁 " if self.is_folder else self._icon()
        tags  = []
        if sensitive:
            tags.append("⚠")
        if manual:
            tags.append("✏")
        tag_str = " ".join(tags)

        display = f"{icon}{self.file_name}"
        if tag_str:
            display += f"  {tag_str}"
        if self.short_desc:
            display += f"\n  {self.short_desc}"

        self.setText(display)
        self.setToolTip(self.short_desc or self.file_name)

    def _icon(self) -> str:
        ext = self.file_name.rsplit(".", 1)[-1].lower() if "." in self.file_name else ""
        icons = {
            "py":"🐍 ", "js":"🟨 ", "ts":"🔷 ", "html":"🌐 ", "css":"🎨 ",
            "json":"📋 ", "yaml":"📋 ", "yml":"📋 ", "md":"📝 ",
            "txt":"📄 ", "pdf":"📕 ", "docx":"📘 ", "csv":"📊 ",
            "xlsx":"📊 ", "png":"🖼 ", "jpg":"🖼 ", "jpeg":"🖼 ",
            "sh":"⚙ ", "cpp":"⚙ ", "go":"🐹 ", "rs":"🦀 ",
            "env":"🔐 ", "sql":"🗃 ",
        }
        return icons.get(ext, "📄 ")


# Main Window 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileSense")
        self.setMinimumSize(1100, 680)
        self.resize(1300, 760)

        self.config    = load_config()
        self.ai_engine = AIEngine(self.config)
        self.watcher   = FolderWatcher(
            self.ai_engine,
            interval_minutes=self.config.get("auto_update_interval_minutes", 30),
            staleness_days  =self.config.get("staleness_days", 4),
        )

        self._current_folder    = ""
        self._current_item      = ""
        self._current_is_folder = True
        # tracks what was selected before entering a side panel
        self._saved_entry:  dict = {}
        self._saved_name:   str  = ""
        self._saved_is_folder: bool = True

        self._setup_ui()
        self._connect_signals()

    # UI construction

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Top-level content stack ───────────────────────────────────────────
        # [0] = main 3-col view   [1] = graph/mind-map
        self._content_stack = QStackedWidget()
        root_layout.addWidget(self._content_stack)

        # Page 0: main 3-column view
        main_page = QWidget()
        mp_layout = QVBoxLayout(main_page)
        mp_layout.setContentsMargins(0, 0, 0, 0)
        mp_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        mp_layout.addWidget(self.splitter)

        # Left: folder tree 
        tree_container = QWidget()
        tree_container.setMinimumWidth(200)
        tree_vbox = QVBoxLayout(tree_container)
        tree_vbox.setContentsMargins(0, 0, 0, 0)
        tree_vbox.setSpacing(0)

        tree_header = QLabel("  FOLDERS")
        tree_header.setFixedHeight(32)
        tree_header.setStyleSheet(
            "background:#1a1b24; color:#4a5070; font-size:10px;"
            "font-weight:700; letter-spacing:1px; border-bottom:1px solid #2a2b3a;"
        )
        tree_vbox.addWidget(tree_header)

        self.fs_model = QFileSystemModel()
        self.fs_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.fs_model.setRootPath("")

        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setRootIndex(self.fs_model.index(""))
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.header().hide()
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        tree_vbox.addWidget(self.tree)

        self.splitter.addWidget(tree_container)

        # Centre: file list
        list_container = QWidget()
        list_container.setMinimumWidth(280)
        list_vbox = QVBoxLayout(list_container)
        list_vbox.setContentsMargins(0, 0, 0, 0)
        list_vbox.setSpacing(0)

        list_hdr_widget = QWidget()
        list_hdr_widget.setFixedHeight(52)
        list_hdr_widget.setStyleSheet(
            "background:#1a1b24; border-bottom:1px solid #2a2b3a;"
        )
        lhw_layout = QVBoxLayout(list_hdr_widget)
        lhw_layout.setContentsMargins(12, 6, 8, 6)
        lhw_layout.setSpacing(2)

        self._folder_name_lbl = QLabel("No folder open")
        self._folder_name_lbl.setStyleSheet(
            "color:#6b7390; font-size:11px; font-weight:600;"
        )
        self._folder_desc_lbl = QLabel("")
        self._folder_desc_lbl.setStyleSheet("color:#4a5070; font-size:10px;")
        self._folder_desc_lbl.setWordWrap(True)

        lhw_layout.addWidget(self._folder_name_lbl)
        lhw_layout.addWidget(self._folder_desc_lbl)
        list_vbox.addWidget(list_hdr_widget)

        self.file_list = QListWidget()
        self.file_list.setUniformItemSizes(False)
        self.file_list.setSpacing(0)
        self.file_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        list_vbox.addWidget(self.file_list)

        self.splitter.addWidget(list_container)

        # Right: stacked subpanel 
        # [0] = description panel   [1] = settings   [2] = edit desc
        self._right_stack = QStackedWidget()

        self.desc_panel = DescriptionPanel()
        self._right_stack.addWidget(self.desc_panel)   # index 0

        self._settings_panel = SettingsPanel()
        self._right_stack.addWidget(self._settings_panel)   # index 1

        self._edit_panel = EditDescPanel()
        self._right_stack.addWidget(self._edit_panel)   # index 2

        self.splitter.addWidget(self._right_stack)
        self.splitter.setSizes([220, 460, 360])

        self._content_stack.addWidget(main_page)   # index 0

        # Page 1: Graph / mind-map view
        graph_page = QWidget()
        graph_page.setStyleSheet("background:#0d0e12;")
        gp_layout  = QVBoxLayout(graph_page)
        gp_layout.setContentsMargins(0, 0, 0, 0)
        gp_layout.setSpacing(0)

        self._mind_map = MindMapWidget()
        gp_layout.addWidget(self._mind_map)

        self._content_stack.addWidget(graph_page)   # index 1

        # Toolbar
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        # Order: Settings | Open Folder | Home | Graph View | Refresh All | Export
        act_settings = QAction("⚙  Settings", self)
        act_settings.setToolTip("Open settings")
        act_settings.triggered.connect(self._open_settings)
        tb.addAction(act_settings)

        tb.addSeparator()

        act_open = QAction("📂  Open Folder", self)
        act_open.setToolTip("Open a folder to annotate")
        act_open.triggered.connect(self._open_folder)
        tb.addAction(act_open)

        tb.addSeparator()

        act_home = QAction("🏠  Home", self)
        act_home.setToolTip(
            "Return to file browser — same folder you were looking at"
        )
        act_home.triggered.connect(self._go_home)
        tb.addAction(act_home)

        tb.addSeparator()

        act_tree = QAction("🌐  Graph View", self)
        act_tree.setToolTip("Open horizontal mind-map for current folder")
        act_tree.triggered.connect(self._open_graph_view)
        tb.addAction(act_tree)

        tb.addSeparator()

        act_refresh = QAction("🔄  Refresh All", self)
        act_refresh.setToolTip("Re-generate all descriptions in current folder")
        act_refresh.triggered.connect(self._refresh_all)
        tb.addAction(act_refresh)

        tb.addSeparator()

        act_export = QAction("📤  Export", self)
        act_export.setToolTip("Save a share-ready sidecar with sensitive data removed")
        act_export.triggered.connect(self._export_share)
        tb.addAction(act_export)

        # right-align the API status chip
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self._api_chip = QLabel()
        self._api_chip.setFixedHeight(22)
        self._update_api_chip()
        tb.addWidget(self._api_chip)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        self._progress = QProgressBar()
        self._progress.setFixedSize(120, 4)
        self._progress.setRange(0, 0)
        self._progress.hide()
        self._status_bar.addPermanentWidget(self._progress)

    def _connect_signals(self):
        # folder tree + file list
        self.tree.clicked.connect(self._on_tree_click)
        self.file_list.currentItemChanged.connect(self._on_file_select)

        # description panel actions
        self.desc_panel.edit_requested.connect(self._edit_description)
        self.desc_panel.ai_refresh_requested.connect(self._ai_refresh_current)
        self.desc_panel.ai_confirm_yes.connect(self._on_ai_confirm_yes)
        self.desc_panel.ai_confirm_no.connect(self._on_ai_confirm_no)
        self.desc_panel.ai_confirm_skip.connect(self._on_ai_confirm_skip)

        # settings panel
        self._settings_panel.saved.connect(self._on_settings_saved)
        self._settings_panel.cancelled.connect(self._go_home)

        # edit description panel
        self._edit_panel.saved.connect(self._on_edit_saved)
        self._edit_panel.cancelled.connect(self._go_home)

        # watcher signals
        self.watcher.status_msg.connect(self._status_bar.showMessage)
        self.watcher.file_refreshed.connect(self._on_file_refreshed)
        self.watcher.folder_refreshed.connect(self._on_folder_refreshed)
        self.watcher.update_started.connect(lambda _: self._progress.show())
        self.watcher.update_finished.connect(lambda _: self._progress.hide())

    # Toolbar actions

    def _go_home(self):
        """Return to main 3-col view, restoring whatever was selected."""
        self._content_stack.setCurrentIndex(0)
        self._right_stack.setCurrentIndex(0)

    def _open_settings(self):
        """Show settings panel inline (replaces right desc panel)."""
        self._content_stack.setCurrentIndex(0)   # ensure main view visible
        self._settings_panel.load()
        self._right_stack.setCurrentIndex(1)

    def _open_graph_view(self):
        if not self._current_folder:
            self._status_bar.showMessage("Open a folder first.")
            return
        self._mind_map.load_folder(self._current_folder)
        self._content_stack.setCurrentIndex(1)

    def _refresh_all(self):
        if not self._current_folder:
            self._status_bar.showMessage("Open a folder first.")
            return
        if not self.ai_engine.is_configured():
            self._status_bar.showMessage("No API key — open Settings first.")
            return
        self.watcher.trigger(self._current_folder, force=True)

    def _export_share(self):
        if not self._current_folder:
            self._status_bar.showMessage("Open a folder first.")
            return
        out_path = export_shareable(self._current_folder)
        self._status_bar.showMessage(f"Exported → {out_path}")

    # Settings

    def _on_settings_saved(self):
        self.config = load_config()
        self.ai_engine.update_config(self.config)
        self.watcher.set_interval(
            self.config.get("auto_update_interval_minutes", 30)
        )
        self._update_api_chip()
        self._go_home()

    # Folder navigation

    def _on_tree_click(self, index: QModelIndex):
        folder_path = self.fs_model.filePath(index)
        self._load_folder(folder_path)

    def _open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Open Folder", "")
        if path:
            idx = self.fs_model.index(path)
            self.tree.setCurrentIndex(idx)
            self.tree.expand(idx)
            self._load_folder(path)

    def _load_folder(self, folder_path: str):
        self._current_folder    = folder_path
        self._current_item      = ""
        self._current_is_folder = True

        self._folder_name_lbl.setText(Path(folder_path).name or folder_path)
        folder_entry = get_folder_entry(folder_path)
        self._folder_desc_lbl.setText(folder_entry.get("short_desc", ""))

        self._populate_file_list(folder_path)
        self.desc_panel.load(folder_entry, Path(folder_path).name, is_folder=True)

        # Return to main view if in graph/settings/edit
        self._go_home()

        self.watcher.watch(folder_path)
        # Fast catch-up: index existing sidecar into SQLite memory (no AI calls)
        self.watcher.index_folder(folder_path)
        if not folder_entry.get("short_desc"):
            if self.ai_engine.is_configured():
                self.watcher.trigger(folder_path, force=False)


    def _populate_file_list(self, folder_path: str):
        self.file_list.clear()
        try:
            items = sorted(os.listdir(folder_path))
        except PermissionError:
            return

        sidecar = load_sidecar(folder_path)

        for name in items:
            if name.startswith("."):
                continue
            full      = os.path.join(folder_path, name)
            is_folder = os.path.isdir(full)
            entry     = (
                sidecar.get("files", {}).get(name, {})
                if not is_folder else {}
            )
            short     = entry.get("short_desc", "")
            sensitive = entry.get("sensitive_detected", False)
            manual    = entry.get("manual_lock", False)
            self.file_list.addItem(FileItem(name, is_folder, short, sensitive, manual))

    # File selection

    def _on_file_select(self, current: QListWidgetItem, _prev):
        if not current or not isinstance(current, FileItem):
            return
        self._current_item      = current.file_name
        self._current_is_folder = current.is_folder

        if current.is_folder:
            sub_path = os.path.join(self._current_folder, current.file_name)
            entry    = get_folder_entry(sub_path)
            self.desc_panel.load(entry, current.file_name, is_folder=True)
        else:
            entry = get_file_entry(self._current_folder, current.file_name)
            self.desc_panel.load(entry, current.file_name, is_folder=False)

        # If a side panel is open, switch back to desc panel on new selection
        if self._right_stack.currentIndex() != 0:
            self._right_stack.setCurrentIndex(0)

    # Watcher callbacks

    def _on_file_refreshed(self, folder: str, filename: str):
        if folder != self._current_folder:
            return
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if isinstance(item, FileItem) and item.file_name == filename:
                entry = get_file_entry(folder, filename)
                item.short_desc = entry.get("short_desc", "")
                item._render(
                    entry.get("sensitive_detected", False),
                    entry.get("manual_lock", False),
                )
                break
        if self._current_item == filename and not self._current_is_folder:
            entry = get_file_entry(folder, filename)
            self.desc_panel.load(entry, filename, is_folder=False)

    def _on_folder_refreshed(self, folder: str):
        if folder != self._current_folder:
            return
        entry = get_folder_entry(folder)
        self._folder_desc_lbl.setText(entry.get("short_desc", ""))
        if not self._current_item:
            self.desc_panel.load(entry, Path(folder).name, is_folder=True)

    # Edit description (inline panel)
    def _edit_description(self):
        if not self._current_folder:
            return

        if self._current_is_folder:
            entry = (
                get_folder_entry(self._current_folder)
                if not self._current_item
                else get_folder_entry(
                    os.path.join(self._current_folder, self._current_item)
                )
            )
            name = self._current_item or Path(self._current_folder).name
        else:
            entry = get_file_entry(self._current_folder, self._current_item)
            name  = self._current_item

        # save reference so _on_edit_saved can use it
        self._saved_entry     = entry
        self._saved_name      = name
        self._saved_is_folder = self._current_is_folder

        self._edit_panel.load(name, entry.get("short_desc", ""), entry.get("long_desc", ""))
        self._right_stack.setCurrentIndex(2)

    def _on_edit_saved(self, short: str, long_: str):
        entry = self._saved_entry
        if self._saved_is_folder:
            if not self._current_item:
                update_folder_desc(
                    self._current_folder, short, long_,
                    manual_lock=True,
                    sensitive_detected=entry.get("sensitive_detected", False),
                )
                self._on_folder_refreshed(self._current_folder)
            else:
                sub = os.path.join(self._current_folder, self._current_item)
                update_folder_desc(
                    sub, short, long_, manual_lock=True,
                    sensitive_detected=entry.get("sensitive_detected", False),
                )
        else:
            update_file_desc(
                self._current_folder, self._current_item,
                short, long_, manual_lock=True,
                sensitive_detected=entry.get("sensitive_detected", False),
                sensitive_types=entry.get("sensitive_types", []),
            )
            self._on_file_refreshed(self._current_folder, self._current_item)

        self._go_home()

    # AI refresh (with inline confirm for manual-locked entries)

    def _ai_refresh_current(self):
        if not self._current_folder:
            return
        if not self.ai_engine.is_configured():
            self._status_bar.showMessage("No API key — open Settings first.")
            return

        entry = (
            get_file_entry(self._current_folder, self._current_item)
            if not self._current_is_folder
            else get_folder_entry(self._current_folder)
        )
        name = self._current_item or Path(self._current_folder).name

        if entry.get("manual_lock"):
            # show inline confirm banner (no popup)
            self.desc_panel.show_ai_confirm(name)
            self._saved_entry     = entry
            self._saved_name      = name
            self._saved_is_folder = self._current_is_folder
            return

        self._start_ai_update()

    def _on_ai_confirm_yes(self):
        self._start_ai_update()

    def _on_ai_confirm_no(self):
        pass   # banner already hidden by desc_panel

    def _on_ai_confirm_skip(self):
        set_manual_lock(
            self._current_folder,
            None if self._current_is_folder else self._current_item,
            locked=False,
        )

    def _start_ai_update(self):
        self.desc_panel.set_loading()
        if self._current_is_folder:
            self.watcher.trigger(self._current_folder, force=True)
        else:
            self._run_single_file_update(self._current_folder, self._current_item)

    def _run_single_file_update(self, folder: str, filename: str):
        class SingleWorker(QThread):
            done = Signal(dict)
            def __init__(self_, fp, ai):
                super().__init__()
                self_.fp = fp; self_.ai = ai
            def run(self_):
                self_.done.emit(self_.ai.describe_file(self_.fp))

        fp = os.path.join(folder, filename)
        w  = SingleWorker(fp, self.ai_engine)

        def on_done(result):
            update_file_desc(
                folder, filename,
                result["short"], result["long"],
                manual_lock=False,
                sensitive_detected=result.get("sensitive_detected", False),
                sensitive_types=result.get("sensitive_types", []),
            )
            self._on_file_refreshed(folder, filename)
            self._status_bar.showMessage("Description updated")
            self._progress.hide()

        w.done.connect(on_done)
        self._progress.show()
        self._status_bar.showMessage(f"Analysing {filename} …")
        w.start()
        self._single_worker = w

    # Misc

    def _update_api_chip(self):
        if self.ai_engine.is_configured():
            self._api_chip.setText("● AI Ready")
            self._api_chip.setStyleSheet(
                "background:#0f2e14; color:#3fb950; border-radius:4px;"
                "padding:0 10px; font-size:10px; font-weight:700;"
            )
        else:
            self._api_chip.setText("● No API Key")
            self._api_chip.setStyleSheet(
                "background:#2a1218; color:#e06060; border-radius:4px;"
                "padding:0 10px; font-size:10px; font-weight:700;"
            )

    def closeEvent(self, event):
        self.watcher.stop_all()
        super().closeEvent(event)
