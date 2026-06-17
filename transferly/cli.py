"""Command-line interface for Transferly."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import questionary
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .config import APP_DIR, CONFIG_DIR, ensure_directories
from .downloads import CURL_CFFI_AVAILABLE, collect_urls, smart_download
from .history import append_history, view_history
from .remotes import browse_remote, list_remotes
from .uploads import stream_upload, upload_file

app = typer.Typer(add_completion=False, help="Smart file transfer tool.")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tsf {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
) -> None:
    """Run the interactive Transferly workflow when no subcommand is provided."""
    ensure_directories()
    if ctx.invoked_subcommand is None:
        interactive()


@app.command("self-update")
def self_update() -> None:
    """Update Transferly in place (stub)."""
    console.print("[yellow]Self-update is not implemented yet.[/yellow]")
    console.print(f"[dim]Install location: {APP_DIR}[/dim]")
    console.print(f"[dim]Config location: {CONFIG_DIR}[/dim]")


def action_stream_to_cloud() -> None:
    entries = collect_urls()
    if not entries:
        return
    remote = questionary.select("Select rclone remote:", choices=list_remotes()).ask()
    folder = browse_remote(remote)
    results = []
    for entry in entries:
        url, filename = entry["url"], entry["filename"]
        start = time.time()
        ok = stream_upload(url, filename, remote, folder)
        elapsed = round(time.time() - start, 1)
        results.append((filename, "✅ OK" if ok else "❌ Failed", f"{elapsed}s"))
        append_history({"action": "stream", "url": url, "filename": filename, "destination": f"{remote}:{folder}", "status": "ok" if ok else "failed"})
    _print_summary(results)


def action_download_upload() -> None:
    entries = collect_urls()
    if not entries:
        return
    remote = questionary.select("Select rclone remote:", choices=list_remotes()).ask()
    folder = browse_remote(remote)
    results = []
    local_files = []
    for entry in entries:
        url, filename = entry["url"], entry["filename"]
        console.print(f"\n[bold cyan]── {filename} ──[/bold cyan]")
        start = time.time()
        dl_ok = smart_download(url, filename)
        up_ok = upload_file(filename, remote, folder) if dl_ok else False
        if dl_ok:
            local_files.append(filename)
        elapsed = round(time.time() - start, 1)
        status = "✅ OK" if (dl_ok and up_ok) else ("⬇ DL Failed" if not dl_ok else "⬆ Upload Failed")
        results.append((filename, status, f"{elapsed}s"))
        append_history({"action": "download_upload", "url": url, "filename": filename, "destination": f"{remote}:{folder}", "status": "ok" if (dl_ok and up_ok) else "failed"})
    _print_summary(results)
    if local_files and questionary.confirm(f"Delete {len(local_files)} local file(s)?", default=True).ask():
        for file in local_files:
            Path(file).unlink(missing_ok=True)
        console.print("[dim]Local files deleted.[/dim]")


def action_download_only() -> None:
    entries = collect_urls()
    if not entries:
        return
    results = []
    for entry in entries:
        url, filename = entry["url"], entry["filename"]
        console.print(f"\n[bold cyan]── {filename} ──[/bold cyan]")
        start = time.time()
        ok = smart_download(url, filename)
        elapsed = round(time.time() - start, 1)
        results.append((filename, "✅ OK" if ok else "❌ Failed", f"{elapsed}s"))
        append_history({"action": "download_only", "url": url, "filename": filename, "status": "ok" if ok else "failed"})
    _print_summary(results)


def action_upload_local() -> None:
    file = questionary.path("Select local file:").ask()
    if not file:
        return
    remote = questionary.select("Select rclone remote:", choices=list_remotes()).ask()
    folder = browse_remote(remote)
    ok = upload_file(file, remote, folder)
    console.print(f"\n{'✅ Uploaded' if ok else '❌ Failed'}: [bold]{file}[/bold] → {remote}:{folder}/")
    append_history({"action": "upload_local", "filename": file, "destination": f"{remote}:{folder}", "status": "ok" if ok else "failed"})


def _print_summary(results: list[tuple[str, str, str]]) -> None:
    table = Table(title="Summary", box=box.SIMPLE_HEAD)
    table.add_column("File", style="bold")
    table.add_column("Status")
    table.add_column("Time", style="dim")
    for row in results:
        table.add_row(*row)
    console.print(table)


def interactive() -> None:
    console.print(Panel(Text("transferly", style="bold cyan", justify="center"), subtitle="[dim]Smart file transfer tool[/dim]", border_style="cyan"))
    if not CURL_CFFI_AVAILABLE:
        console.print("[dim yellow]⚠  curl_cffi not found — CF bypass disabled. Install: pip install curl-cffi[/dim yellow]\n")
    try:
        while True:
            choice = questionary.select(
                "Select action",
                choices=["⚡ Stream URL → Cloud", "⬇  Download URL → Upload", "📥 Download URL only", "📤 Upload local file", "📋 View history", "🚪 Exit"],
            ).ask()
            if choice and "Stream" in choice:
                action_stream_to_cloud()
            elif choice and "Download URL → Upload" in choice:
                action_download_upload()
            elif choice and "Download URL only" in choice:
                action_download_only()
            elif choice and "Upload local" in choice:
                action_upload_local()
            elif choice and "history" in choice:
                view_history()
            elif choice and "Exit" in choice:
                console.print("[yellow]Goodbye 👋[/yellow]")
                sys.exit()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        sys.exit()


def run() -> None:
    app()


if __name__ == "__main__":
    run()
