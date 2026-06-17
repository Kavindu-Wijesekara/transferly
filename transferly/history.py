"""SQLite transfer history persistence and display."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from rich import box
from rich.console import Console
from rich.table import Table

from .config import HISTORY_FILE, ensure_config_dir, load_config
from .security import sanitize_url

console = Console()

SCHEMA = """
CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source_url TEXT,
    filename TEXT NOT NULL,
    remote TEXT,
    destination TEXT,
    transfer_type TEXT NOT NULL,
    status TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    ensure_config_dir()
    conn = sqlite3.connect(HISTORY_FILE)
    conn.execute(SCHEMA)
    return conn


def append_history(entry: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO transfers (timestamp, source_url, filename, remote, destination, transfer_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.get("timestamp", datetime.now().isoformat()),
                sanitize_url(entry.get("source_url") or entry.get("url") or ""),
                entry.get("filename", ""),
                entry.get("remote", ""),
                entry.get("destination", ""),
                entry.get("transfer_type") or entry.get("action", "unknown"),
                entry.get("status", "unknown"),
            ),
        )


def view_history() -> None:
    limit = int(load_config().get("history_limit", 20))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, transfer_type, filename, remote, destination, status
            FROM transfers ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    if not rows:
        console.print("[dim]No history yet.[/dim]")
        return

    table = Table(title="Transfer History", box=box.ROUNDED, show_lines=True)
    table.add_column("Time", style="dim", width=20)
    table.add_column("Type", style="cyan", width=18)
    table.add_column("File", style="bold", width=28)
    table.add_column("Remote", width=14)
    table.add_column("Destination", width=28)
    table.add_column("Status", width=10)
    for timestamp, transfer_type, filename, remote, destination, status in rows:
        status_style = "green" if status == "ok" else "red"
        table.add_row(timestamp[:19], transfer_type, filename, remote or "—", destination or "—", f"[{status_style}]{status}[/{status_style}]")
    console.print(table)
