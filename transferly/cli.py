"""Command-line interface for Transferly."""

from __future__ import annotations

import subprocess
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
from .config import APP_DIR, CONFIG_DIR, ensure_directories, load_config, save_config
from .downloads import UrlEntry, collect_urls, smart_download
from .history import append_history, view_history
from .processes import SUPERVISOR
from .remotes import browse_remote, list_remotes
from .uploads import stream_upload, upload_file

app = typer.Typer(add_completion=False, help="Transferly smart file transfer manager.")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"tsf {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit.")) -> None:
    ensure_directories()
    if ctx.invoked_subcommand is None:
        interactive()


@app.command("self-update")
def self_update() -> None:
    """Pull the latest application code and refresh dependencies while preserving config."""
    app_path = APP_DIR / "app"
    if not (app_path / ".git").exists():
        console.print("[yellow]Self-update requires a git checkout installed in ~/.transferly/app.[/yellow]")
        return
    subprocess.run(["git", "-C", str(app_path), "pull", "--ff-only"], check=False)
    subprocess.run([str(APP_DIR / "venv" / "bin" / "pip"), "install", "-r", str(app_path / "requirements.txt")], check=False)
    console.print("[green]Transferly update complete.[/green]")


def _select_remote_and_folder() -> tuple[str, str] | None:
    remotes = list_remotes()
    if not remotes:
        console.print("[red]No rclone remotes found. Run `rclone config` first.[/red]")
        return None
    cfg = load_config()
    default_remote = cfg.get("default_remote") if cfg.get("default_remote") in remotes else None
    remote = questionary.select("Select rclone remote:", choices=remotes, default=default_remote).ask()
    if not remote:
        return None
    folder = browse_remote(remote)
    if folder is None:
        console.print("[yellow]Action cancelled.[/yellow]")
        return None
    return remote, folder


def action_stream_to_cloud() -> None:
    entries = collect_urls()
    selected = _select_remote_and_folder() if entries else None
    if not selected:
        return
    remote, folder = selected
    results = []
    for entry in entries:
        start = time.time()
        ok = stream_upload(entry.url, entry.filename, remote, folder, entry.auth)
        elapsed = round(time.time() - start, 1)
        results.append((entry.filename, "✅ OK" if ok else "❌ Failed", f"{elapsed}s"))
        append_history({"transfer_type": "stream", "source_url": entry.url, "filename": entry.filename, "remote": remote, "destination": f"{remote}:{folder}", "status": "ok" if ok else "failed"})
    _print_summary(results)


def action_download_upload() -> None:
    entries = collect_urls()
    selected = _select_remote_and_folder() if entries else None
    if not selected:
        return
    remote, folder = selected
    cfg = load_config()
    local_files: list[str] = []
    results = []
    for entry in entries:
        console.print(f"\n[bold cyan]── {entry.filename} ──[/bold cyan]")
        start = time.time()
        ok_download = smart_download(entry.url, entry.filename, entry.auth)
        ok_upload = upload_file(entry.filename, remote, folder) if ok_download else False
        if ok_download:
            local_files.append(entry.filename)
        elapsed = round(time.time() - start, 1)
        results.append((entry.filename, "✅ OK" if ok_download and ok_upload else "❌ Failed", f"{elapsed}s"))
        append_history({"transfer_type": "download_upload", "source_url": entry.url, "filename": entry.filename, "remote": remote, "destination": f"{remote}:{folder}", "status": "ok" if ok_download and ok_upload else "failed"})
    _print_summary(results)
    cleanup_default = bool(cfg.get("default_cleanup", True))
    if local_files and questionary.confirm(f"Delete {len(local_files)} local file(s)?", default=cleanup_default).ask():
        for file in local_files:
            Path(file).unlink(missing_ok=True)
        console.print("[dim]Local files deleted.[/dim]")


def action_download_only() -> None:
    entries = collect_urls()
    results = []
    for entry in entries:
        console.print(f"\n[bold cyan]── {entry.filename} ──[/bold cyan]")
        start = time.time()
        ok = smart_download(entry.url, entry.filename, entry.auth)
        elapsed = round(time.time() - start, 1)
        results.append((entry.filename, "✅ OK" if ok else "❌ Failed", f"{elapsed}s"))
        append_history({"transfer_type": "download_only", "source_url": entry.url, "filename": entry.filename, "status": "ok" if ok else "failed"})
    _print_summary(results)


def action_upload_local() -> None:
    file = questionary.path("Select local file:").ask()
    selected = _select_remote_and_folder() if file else None
    if not selected:
        return
    remote, folder = selected
    ok = upload_file(file, remote, folder)
    console.print(f"\n{'✅ Uploaded' if ok else '❌ Failed'}: [bold]{file}[/bold] → {remote}:{folder}/")
    append_history({"transfer_type": "upload_local", "filename": Path(file).name, "remote": remote, "destination": f"{remote}:{folder}", "status": "ok" if ok else "failed"})


def action_browse_cloud_storage() -> None:
    _select_remote_and_folder()


def action_settings() -> None:
    cfg = load_config()
    while True:
        choice = questionary.select("Settings", choices=["Default remote", "Default transfer mode", "Default cleanup behavior", "Download directory", "History limit", "Back"]).ask()
        if choice == "Back" or choice is None:
            save_config(cfg)
            return
        if choice == "Default remote":
            remotes = list_remotes()
            cfg["default_remote"] = questionary.select("Default remote:", choices=[""] + remotes).ask() or ""
        elif choice == "Default transfer mode":
            cfg["default_transfer_mode"] = questionary.select("Default transfer mode:", choices=["Stream URL → Cloud", "Download URL → Upload", "Download URL Only", "Upload Local File"]).ask()
        elif choice == "Default cleanup behavior":
            cfg["default_cleanup"] = questionary.confirm("Delete local files after upload by default?", default=bool(cfg.get("default_cleanup", True))).ask()
        elif choice == "Download directory":
            cfg["download_directory"] = questionary.path("Download directory:", default=cfg.get("download_directory", str(Path.cwd()))).ask()
        elif choice == "History limit":
            cfg["history_limit"] = int(questionary.text("History rows to show:", default=str(cfg.get("history_limit", 20))).ask() or 20)
        save_config(cfg)


def _print_summary(results: list[tuple[str, str, str]]) -> None:
    table = Table(title="Summary", box=box.SIMPLE_HEAD)
    table.add_column("File", style="bold")
    table.add_column("Status")
    table.add_column("Time", style="dim")
    for row in results:
        table.add_row(*row)
    console.print(table)


def interactive() -> None:
    console.print(Panel(Text("Transferly", style="bold cyan", justify="center"), subtitle="[dim]aria2 + rclone transfer manager[/dim]", border_style="cyan"))
    try:
        while True:
            choice = questionary.select(
                "Select Action",
                choices=["1. Stream URL → Cloud", "2. Download URL → Upload", "3. Download URL Only", "4. Upload Local File", "5. Browse Cloud Storage", "6. Transfer History", "7. Settings", "8. Exit"],
            ).ask()
            if not choice or choice.endswith("Exit"):
                console.print("[yellow]Goodbye 👋[/yellow]")
                return
            if "Stream" in choice:
                action_stream_to_cloud()
            elif "Download URL → Upload" in choice:
                action_download_upload()
            elif "Download URL Only" in choice:
                action_download_only()
            elif "Upload Local" in choice:
                action_upload_local()
            elif "Browse Cloud" in choice:
                action_browse_cloud_storage()
            elif "Transfer History" in choice:
                view_history()
            elif "Settings" in choice:
                action_settings()
    except KeyboardInterrupt:
        SUPERVISOR.cancel()
        raise typer.Exit(130)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
