"""Configuration paths and helpers for Transferly."""

from __future__ import annotations

import json
from pathlib import Path

APP_DIR = Path.home() / ".transferly"
CONFIG_DIR = Path.home() / ".config" / "transferly"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def ensure_directories() -> None:
    ensure_app_dir()
    ensure_config_dir()


def load_config() -> dict:
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
