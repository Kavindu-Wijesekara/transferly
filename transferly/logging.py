"""Transferly logging with secret redaction."""

from __future__ import annotations

from datetime import datetime

from .config import LOG_DIR, ensure_directories
from .security import sanitize_text


def log_event(kind: str, message: object) -> None:
    ensure_directories()
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    timestamp = datetime.now().isoformat(timespec="seconds")
    log_file.open("a", encoding="utf-8").write(f"{timestamp} [{kind}] {sanitize_text(message)}\n")
