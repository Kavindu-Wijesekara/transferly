"""Transfer history persistence and display."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from rich import box
from rich.console import Console
from rich.table import Table

from .config import HISTORY_FILE, ensure_config_dir

console = Console()


def append_history(entry: dict[str, Any]) -> None:
    ensure_config_dir()
    history: list[dict[str, Any]] = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            history = []
    entry.setdefault("timestamp", datetime.now().isoformat())
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def view_history() -> None:
    if not HISTORY_FILE.exists():
        console.print("[dim]No history yet.[/dim]")
        return

    history = json.loads(HISTORY_FILE.read_text())
    if not history:
        console.print("[dim]History is empty.[/dim]")
        return

    table = Table(title="Transfer History", box=box.ROUNDED, show_lines=True)
    table.add_column("Time", style="dim", width=20)
    table.add_column("Action", style="cyan", width=16)
    table.add_column("File", style="bold", width=30)
    table.add_column("Destination", width=28)
    table.add_column("Status", width=10)

    for h in reversed(history[-20:]):
        status_style = "green" if h.get("status") == "ok" else "red"
        table.add_row(
            h.get("timestamp", "")[:19],
            h.get("action", ""),
            h.get("filename", ""),
            h.get("destination", "—"),
            f"[{status_style}]{h.get('status', '?')}[/{status_style}]",
        )

    console.print(table)
