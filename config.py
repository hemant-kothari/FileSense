import json
from pathlib import Path

APP_NAME = "FolderScribe"
APP_VERSION = "1.0.0"
SIDECAR_FILENAME = ".folderscribe.json"
CONFIG_DIR = Path.home() / ".folderscribe"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "groq_api_key": "",
    "groq_model": "llama-3.1-8b-instant",
    "groq_vision_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "auto_update_interval_minutes": 30,
    "staleness_days": 4,
    "max_text_chars": 3000,
    "max_tail_chars": 500,
    "max_csv_rows": 20,
    "max_file_size_mb": 10,
}

# Models that no longer exist — map old name → replacement
_DEPRECATED_MODELS = {
    "llama3-8b-8192":              "llama-3.1-8b-instant",
    "llama3-70b-8192":             "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768":          "llama-3.3-70b-versatile",
    "gemma-7b-it":                 "llama-3.1-8b-instant",
    "gemma2-9b-it":                "llama-3.1-8b-instant",
    "llava-v1.5-7b-4096-preview":  "meta-llama/llama-4-scout-17b-16e-instruct",
}


def _migrate(cfg: dict) -> dict:
    """Replace any decommissioned model names saved in config."""
    changed = False
    for key in ("groq_model", "groq_vision_model"):
        old = cfg.get(key, "")
        if old in _DEPRECATED_MODELS:
            cfg[key] = _DEPRECATED_MODELS[old]
            changed = True
    if changed:
        save_config(cfg)
    return cfg


def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return _migrate(cfg)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
