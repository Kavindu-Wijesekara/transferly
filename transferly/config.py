"""Configuration paths and helpers for Transferly."""

from __future__ import annotations

import json
from pathlib import Path

APP_DIR = Path.home() / ".transferly"
CONFIG_DIR = Path.home() / ".config" / "transferly"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.db"
LOG_DIR = CONFIG_DIR / "logs"
DEFAULT_CONFIG = {
    "default_remote": "",
    "default_transfer_mode": "Stream URL → Cloud",
    "default_cleanup": True,
    "download_directory": str(Path.cwd()),
    "history_limit": 20,
    "last_folder": {},
}


def ensure_directories() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def ensure_config_dir() -> None:
    ensure_directories()


def load_config() -> dict:
    ensure_directories()
    if CONFIG_FILE.exists():
        try:
            return DEFAULT_CONFIG | json.loads(CONFIG_FILE.read_text())
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    ensure_directories()
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG | cfg, indent=2))
