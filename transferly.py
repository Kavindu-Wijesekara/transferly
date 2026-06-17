#!/home/dev/transferly-env/bin/python

import subprocess
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import questionary
from rich import print
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

try:
    from curl_cffi import requests as cf_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

import requests as std_requests

console = Console()

# ─────────────────────────────────────────────
# Config & History
# ─────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".transferly"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"


def ensure_config_dir():
    CONFIG_DIR.mkdir(exist_ok=True)


def load_config() -> dict:
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def append_history(entry: dict):
    ensure_config_dir()
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            history = []
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


# ─────────────────────────────────────────────
# Shell helpers
# ─────────────────────────────────────────────

def run(cmd: list, silent=False) -> bool:
    try:
        kwargs = {}
        if silent:
            kwargs["stdout"] = subprocess.DEVNULL
            kwargs["stderr"] = subprocess.DEVNULL
        subprocess.run(cmd, check=True, **kwargs)
        return True
    except subprocess.CalledProcessError:
        return False


def run_shell(cmd: str) -> bool:
    try:
        subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def run_output(cmd: list) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip()


# ─────────────────────────────────────────────
# URL & filename helpers
# ─────────────────────────────────────────────

def detect_filename(url: str) -> str:
    """Follow redirects and extract final filename from URL path."""
    try:
        r = std_requests.get(url, allow_redirects=True, stream=True, timeout=10)
        final_url = r.url
        name = Path(urlparse(final_url).path).name
        return name if name else "download"
    except Exception:
        name = Path(urlparse(url).path).name
        return name if name else "download"


def is_cloudflare_blocked(file_path: str) -> bool:
    """Check if a downloaded file is actually a Cloudflare challenge page."""
    try:
        p = Path(file_path)
        if not p.exists() or p.stat().st_size > 100_000:
            return False
        content = p.read_text(errors="ignore").lower()
        markers = ["just a moment", "cf-browser-verification", "enable javascript", "checking your browser"]
        return any(m in content for m in markers)
    except Exception:
        return False


# ─────────────────────────────────────────────
# Download strategies
# ─────────────────────────────────────────────

def download_aria2c(url: str, filename: str) -> bool:
    """Primary downloader using aria2c."""
    console.print("[cyan]⬇  Trying aria2c...[/cyan]")
    success = run([
        "aria2c",
        "-o", filename,
        "-x", "4",
        "-s", "4",
        "--min-split-size=50M",
        "--retry-wait=5",
        "--max-tries=3",
        "--auto-file-renaming=false",
        url
    ])
    if not success:
        return False
    if is_cloudflare_blocked(filename):
        Path(filename).unlink(missing_ok=True)
        return False
    return True


def download_curl_cffi(url: str, filename: str) -> bool:
    """Fallback downloader using curl_cffi (bypasses Cloudflare JS challenges)."""
    if not CURL_CFFI_AVAILABLE:
        console.print("[red]curl_cffi not installed. Run: pip install curl-cffi[/red]")
        return False

    console.print("[yellow]⬇  aria2c failed or blocked. Trying curl_cffi (CF bypass)...[/yellow]")
    try:
        with cf_requests.Session(impersonate="chrome120") as session:
            r = session.get(url, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            print(f"\r  [green]{pct:.1f}%[/green] — {downloaded // (1024*1024)} MB / {total // (1024*1024)} MB", end="")
            print()
        return True
    except Exception as e:
        console.print(f"[red]curl_cffi failed: {e}[/red]")
        return False


def smart_download(url: str, filename: str) -> bool:
    """Try aria2c first, fall back to curl_cffi on failure."""
    if download_aria2c(url, filename):
        return True
    return download_curl_cffi(url, filename)


# ─────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────

def upload_file(file: str, remote: str, folder: str) -> bool:
    console.print(f"[green]⬆  Uploading [bold]{file}[/bold] → {remote}:{folder}/[/green]")
    dest = f"{remote}:{folder}/{file}"
    return run([
        "rclone", "copyto", file, dest,
        "--drive-chunk-size", "128M",
        "--transfers", "4",
        "--checkers", "8",
        "-P"
    ])


# ─────────────────────────────────────────────
# Stream (fixed: curl instead of aria2c stdout)
# ─────────────────────────────────────────────

def stream_upload(url: str, filename: str, remote: str, folder: str) -> bool:
    """
    Stream URL directly to cloud using curl pipe → rclone rcat.
    aria2c does not reliably support stdout (-o -), so we use curl here.
    curl_cffi fallback is applied if curl exits non-zero.
    """
    dest = f"{remote}:{folder}/{filename}"
    console.print(f"[cyan]⚡ Streaming [bold]{filename}[/bold] → {dest}[/cyan]")

    # Primary: curl pipe
    curl_cmd = (
        f'curl -L --retry 3 --retry-wait 5 -A "Mozilla/5.0" '
        f'--fail --silent --show-error "{url}" | rclone rcat "{dest}" -P'
    )
    if run_shell(curl_cmd):
        return True

    # Fallback: curl_cffi stream → rclone rcat via stdin
    if CURL_CFFI_AVAILABLE:
        console.print("[yellow]curl stream failed. Trying curl_cffi stream fallback...[/yellow]")
        try:
            with cf_requests.Session(impersonate="chrome120") as session:
                r = session.get(url, stream=True, timeout=30)
                r.raise_for_status()
                rclone_proc = subprocess.Popen(
                    ["rclone", "rcat", dest, "-P"],
                    stdin=subprocess.PIPE
                )
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        rclone_proc.stdin.write(chunk)
                rclone_proc.stdin.close()
                rclone_proc.wait()
                return rclone_proc.returncode == 0
        except Exception as e:
            console.print(f"[red]Stream fallback failed: {e}[/red]")

    return False


# ─────────────────────────────────────────────
# Rclone remote browser
# ─────────────────────────────────────────────

def list_remotes() -> list[str]:
    out = run_output(["rclone", "listremotes"])
    return [r.replace(":", "") for r in out.splitlines()]


def list_dirs(remote: str, path: str = "") -> list[str]:
    target = f"{remote}:{path}" if path else f"{remote}:"
    out = run_output(["rclone", "lsf", target, "--dirs-only"])
    return [d.strip("/") for d in out.splitlines()]


def browse_remote(remote: str) -> str:
    current = ""
    cfg = load_config()
    last_folder = cfg.get("last_folder", {}).get(remote, "")

    if last_folder:
        use_last = questionary.confirm(
            f"Use last folder? [{remote}:{last_folder}]"
        ).ask()
        if use_last:
            return last_folder

    while True:
        dirs = list_dirs(remote, current)
        choices = []
        if current:
            choices.append(".. (back)")
        choices += dirs
        choices += ["[Create folder]", "[Select this folder]", "[Cancel]"]

        choice = questionary.select(
            f"📁 {remote}:{current or '/'}",
            choices=choices
        ).ask()

        if choice == "[Cancel]":
            sys.exit()
        elif choice == ".. (back)":
            current = "/".join(current.split("/")[:-1])
        elif choice == "[Create folder]":
            name = questionary.text("Folder name:").ask()
            run(["rclone", "mkdir", f"{remote}:{current}/{name}"])
            current = f"{current}/{name}".strip("/")
        elif choice == "[Select this folder]":
            cfg.setdefault("last_folder", {})[remote] = current
            save_config(cfg)
            return current
        else:
            current = f"{current}/{choice}".strip("/")


# ─────────────────────────────────────────────
# URL input: multiline batch
# ─────────────────────────────────────────────

def collect_urls() -> list[dict]:
    """
    Collect one or more URLs via multiline paste.
    Returns list of {url, filename} dicts with rename applied.
    """
    console.print(Panel(
        "[dim]Paste one or more URLs (one per line).\nPress [bold]Enter twice[/bold] (blank line) when done.[/dim]",
        title="URL Input",
        border_style="cyan"
    ))

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            if lines:
                break
        else:
            lines.append(line.strip())

    urls = [l for l in lines if l.startswith("http")]

    if not urls:
        console.print("[red]No valid URLs found.[/red]")
        return []

    console.print(f"\n[green]Found {len(urls)} URL(s)[/green]\n")

    # Show detected filenames and ask for renames
    entries = []
    for url in urls:
        detected = detect_filename(url)
        console.print(f"  [dim]URL:[/dim] {url[:70]}{'...' if len(url) > 70 else ''}")
        console.print(f"  [dim]Detected filename:[/dim] [bold]{detected}[/bold]")
        rename = questionary.text(
            f"  Rename? (leave empty to keep '{detected}')"
        ).ask()
        filename = rename.strip() if rename and rename.strip() else detected
        entries.append({"url": url, "filename": filename})
        console.print()

    return entries


# ─────────────────────────────────────────────
# Single URL input (for download-only)
# ─────────────────────────────────────────────

def collect_single_url() -> dict | None:
    url = questionary.text("Download URL:").ask()
    if not url:
        return None
    detected = detect_filename(url)
    rename = questionary.text(
        f"Rename file? (leave empty to keep '{detected}')"
    ).ask()
    filename = rename.strip() if rename and rename.strip() else detected
    return {"url": url, "filename": filename}


# ─────────────────────────────────────────────
# Actions
# ─────────────────────────────────────────────

def action_stream_to_cloud():
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
        status = "✅ OK" if ok else "❌ Failed"
        results.append((filename, status, f"{elapsed}s"))
        append_history({
            "action": "stream",
            "url": url,
            "filename": filename,
            "destination": f"{remote}:{folder}",
            "status": "ok" if ok else "failed",
            "timestamp": datetime.now().isoformat()
        })

    _print_summary(results)


def action_download_upload():
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

        if dl_ok:
            up_ok = upload_file(filename, remote, folder)
            local_files.append(filename)
        else:
            up_ok = False

        elapsed = round(time.time() - start, 1)
        status = "✅ OK" if (dl_ok and up_ok) else ("⬇ DL Failed" if not dl_ok else "⬆ Upload Failed")
        results.append((filename, status, f"{elapsed}s"))
        append_history({
            "action": "download_upload",
            "url": url,
            "filename": filename,
            "destination": f"{remote}:{folder}",
            "status": "ok" if (dl_ok and up_ok) else "failed",
            "timestamp": datetime.now().isoformat()
        })

    _print_summary(results)

    if local_files:
        delete = questionary.confirm(
            f"Delete {len(local_files)} local file(s)?", default=True
        ).ask()
        if delete:
            for f in local_files:
                Path(f).unlink(missing_ok=True)
            console.print("[dim]Local files deleted.[/dim]")


def action_download_only():
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
        status = "✅ OK" if ok else "❌ Failed"
        results.append((filename, status, f"{elapsed}s"))
        append_history({
            "action": "download_only",
            "url": url,
            "filename": filename,
            "status": "ok" if ok else "failed",
            "timestamp": datetime.now().isoformat()
        })

    _print_summary(results)


def action_upload_local():
    file = questionary.path("Select local file:").ask()
    if not file:
        return
    remote = questionary.select("Select rclone remote:", choices=list_remotes()).ask()
    folder = browse_remote(remote)
    ok = upload_file(file, remote, folder)
    status = "✅ Uploaded" if ok else "❌ Failed"
    console.print(f"\n{status}: [bold]{file}[/bold] → {remote}:{folder}/")
    append_history({
        "action": "upload_local",
        "filename": file,
        "destination": f"{remote}:{folder}",
        "status": "ok" if ok else "failed",
        "timestamp": datetime.now().isoformat()
    })


def action_view_history():
    if not HISTORY_FILE.exists():
        console.print("[dim]No history yet.[/dim]")
        return

    history = json.loads(HISTORY_FILE.read_text())
    if not history:
        console.print("[dim]History is empty.[/dim]")
        return

    table = Table(
        title="Transfer History",
        box=box.ROUNDED,
        show_lines=True
    )
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
            f"[{status_style}]{h.get('status', '?')}[/{status_style}]"
        )

    console.print(table)


# ─────────────────────────────────────────────
# Summary table
# ─────────────────────────────────────────────

def _print_summary(results: list[tuple]):
    table = Table(title="Summary", box=box.SIMPLE_HEAD)
    table.add_column("File", style="bold")
    table.add_column("Status")
    table.add_column("Time", style="dim")
    for row in results:
        table.add_row(*row)
    console.print(table)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    console.print(Panel(
        Text("transferly", style="bold cyan", justify="center"),
        subtitle="[dim]Smart file transfer tool[/dim]",
        border_style="cyan"
    ))

    if not CURL_CFFI_AVAILABLE:
        console.print("[dim yellow]⚠  curl_cffi not found — CF bypass disabled. Install: pip install curl-cffi[/dim yellow]\n")

    try:
        while True:
            choice = questionary.select(
                "Select action",
                choices=[
                    "⚡ Stream URL → Cloud",
                    "⬇  Download URL → Upload",
                    "📥 Download URL only",
                    "📤 Upload local file",
                    "📋 View history",
                    "🚪 Exit"
                ]
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
                action_view_history()
            elif choice and "Exit" in choice:
                console.print("[yellow]Goodbye 👋[/yellow]")
                sys.exit()

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        sys.exit()


if __name__ == "__main__":
    main()
