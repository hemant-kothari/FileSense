# Sidecar — read/write .filesense.json metadata files.


import copy
import json
import os
from datetime import datetime
from pathlib import Path

from config import SIDECAR_FILENAME


# Sidecar path helpers 

def _sidecar_path(folder_path: str) -> Path:
    return Path(folder_path) / SIDECAR_FILENAME


def _empty() -> dict:
    return {"version": "2.0", "folder": {}, "files": {}}



# Load / Save

def load_sidecar(folder_path: str) -> dict:
    p = _sidecar_path(folder_path)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _empty()


def save_sidecar(folder_path: str, data: dict):
    p = _sidecar_path(folder_path)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[sidecar] save error: {e}")


# mtime helpers

def _file_mtime_iso(folder_path: str, filename: str) -> str:
    try:
        path = Path(folder_path) / filename
        return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
    except Exception:
        return ""


def _days_since_modified(folder_path: str, filename: str) -> float:
    try:
        path = Path(folder_path) / filename
        mtime = os.path.getmtime(path)
        return (datetime.now().timestamp() - mtime) / 86400
    except Exception:
        return 0.0


# Read

def get_file_entry(folder_path: str, filename: str) -> dict:
    return load_sidecar(folder_path).get("files", {}).get(filename, {})


def get_folder_entry(folder_path: str) -> dict:
    return load_sidecar(folder_path).get("folder", {})


def get_file_history(folder_path: str, filename: str) -> list[dict]:
    """Return the portable history list stored in the sidecar (up to 5 entries)."""
    return load_sidecar(folder_path).get("files", {}).get(filename, {}).get("history", [])


# Write

def _push_history(existing_entry: dict, short: str, long_: str, source: str) -> list:
    """
    Push the *current* description of an existing entry into the history ring
    buffer before overwriting it.  Keeps the newest 5 entries.
    """
    history = list(existing_entry.get("history", []))

    old_short = existing_entry.get("short_desc", "")
    old_long  = existing_entry.get("long_desc", "")
    old_ts    = existing_entry.get("last_updated", "")
    old_src   = "manual" if existing_entry.get("manual_lock") else "ai"

    # Only push if there was a real previous description
    if old_short and old_short != short:
        history.insert(0, {
            "short":       old_short,
            "long":        old_long,
            "source":      old_src,
            "recorded_at": old_ts or datetime.now().isoformat(),
        })

    return history[:5]   # keep newest 5


def update_file_desc(
    folder_path: str,
    filename: str,
    short_desc: str,
    long_desc: str,
    manual_lock: bool = False,
    sensitive_detected: bool = False,
    sensitive_types: list = None,
    tags: list = None,
    narrative: str = "",
    last_error: str = "",
):
    """
    Persist a file description to the sidecar.

    New in v2:
      • tags       — AI-generated semantic tags (list of str)
      • narrative  — rolling evolution summary (60–200 words)
      • last_error — error message if AI generation failed
      • history    — previous description pushed automatically
    """
    data     = load_sidecar(folder_path)
    existing = data.setdefault("files", {}).get(filename, {})

    # Preserve manual_lock unless caller explicitly sets it
    if not manual_lock:
        manual_lock = existing.get("manual_lock", False)

    # Push previous description into portable history ring
    history = _push_history(existing, short_desc, long_desc,
                             source="manual" if manual_lock else "ai")

    data["files"][filename] = {
        "short_desc":         short_desc,
        "long_desc":          long_desc,
        "narrative":          narrative or existing.get("narrative", ""),
        "tags":               list(tags) if tags is not None else existing.get("tags", []),
        "manual_lock":        manual_lock,
        "last_updated":       datetime.now().isoformat(),
        "last_file_modified": _file_mtime_iso(folder_path, filename),
        "sensitive_detected": sensitive_detected,
        "sensitive_types":    sensitive_types or [],
        "last_error":         last_error,
        "history":            history,
    }
    save_sidecar(folder_path, data)


def update_file_narrative(folder_path: str, filename: str, narrative: str):
    """Lightweight update — only write the narrative without touching other fields."""
    data = load_sidecar(folder_path)
    data.setdefault("files", {}).setdefault(filename, {})["narrative"] = narrative
    save_sidecar(folder_path, data)


def update_folder_desc(
    folder_path: str,
    short_desc: str,
    long_desc: str,
    manual_lock: bool = False,
    sensitive_detected: bool = False,
    tags: list = None,
):
    data     = load_sidecar(folder_path)
    existing = data.get("folder", {})
    if not manual_lock:
        manual_lock = existing.get("manual_lock", False)

    data["folder"] = {
        "short_desc":       short_desc,
        "long_desc":        long_desc,
        "tags":             list(tags) if tags is not None else existing.get("tags", []),
        "manual_lock":      manual_lock,
        "last_updated":     datetime.now().isoformat(),
        "sensitive_detected": sensitive_detected,
    }
    save_sidecar(folder_path, data)


def set_manual_lock(folder_path: str, filename: str | None, locked: bool):
    data = load_sidecar(folder_path)
    if filename:
        data.setdefault("files", {}).setdefault(filename, {})["manual_lock"] = locked
    else:
        data.setdefault("folder", {})["manual_lock"] = locked
    save_sidecar(folder_path, data)


#  Staleness check

def needs_update(folder_path: str, filename: str, staleness_days: int = 4) -> bool:
    """
    Returns True if the file should be re-described.
    False if: manual_lock, not recently modified (idle > staleness_days), or mtime unchanged.
    """
    data  = load_sidecar(folder_path)
    entry = data.get("files", {}).get(filename)

    if entry is None:
        return True   # never described

    if entry.get("manual_lock", False):
        return False

    days_idle = _days_since_modified(folder_path, filename)
    if days_idle > staleness_days:
        return False  # file hasn't been touched — stop auto-updating

    stored_mtime  = entry.get("last_file_modified", "")
    current_mtime = _file_mtime_iso(folder_path, filename)
    return stored_mtime != current_mtime


# Share export 

def export_shareable(folder_path: str, output_path: str | None = None) -> str:
    """
    Write a sanitised copy of the sidecar with sensitive-data entries scrubbed
    and history removed (may contain private details).
    Returns the path of the written file.
    """
    data = copy.deepcopy(load_sidecar(folder_path))

    folder_entry = data.get("folder", {})
    if folder_entry.get("sensitive_detected"):
        folder_entry["short_desc"] = "[Sensitive data detected — removed for sharing]"
        folder_entry["long_desc"]  = ""
    folder_entry.pop("sensitive_detected", None)
    folder_entry.pop("sensitive_types",    None)

    for _fname, entry in data.get("files", {}).items():
        if entry.get("sensitive_detected"):
            entry["short_desc"] = "[Contains sensitive data]"
            entry["long_desc"]  = ""
            entry["narrative"]  = ""
        entry.pop("sensitive_detected", None)
        entry.pop("sensitive_types",    None)
        entry.pop("last_error",         None)
        entry.pop("history",            None)   # strip history for privacy

    if output_path is None:
        output_path = str(Path(folder_path) / ".filesense.share.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path
