"""Download helpers, filename detection, and URL input flows."""

from __future__ import annotations

import email.message
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import questionary
import requests
from rich.console import Console
from rich.panel import Panel

from .auth import AuthConfig, prompt_auth
from .config import load_config
from .processes import run_checked
from .logging import log_event
from .security import sanitize_text, sanitize_url

console = Console()
RETRYABLE_STATUS_MARKERS = ("401", "403", "429", "503")
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"


@dataclass
class UrlEntry:
    url: str
    filename: str
    auth: AuthConfig


def run(cmd: list[str], silent: bool = False) -> bool:
    stdout = subprocess.DEVNULL if silent else None
    stderr = subprocess.DEVNULL if silent else None
    return subprocess.run(cmd, stdout=stdout, stderr=stderr).returncode == 0


def run_output(cmd: list[str]) -> str:
    result = run_checked(cmd, capture_output=True)
    return result.stdout.strip() if result.stdout else ""


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    msg = email.message.Message()
    msg["content-disposition"] = value
    filename = msg.get_filename()
    return Path(filename).name if filename else None


def _filename_from_url(url: str) -> str | None:
    name = Path(unquote(urlparse(url).path)).name
    return name or None


def detect_filename(url: str, auth: AuthConfig | None = None) -> str | None:
    """Return filename from Content-Disposition, final redirect URL, or None."""
    headers = {}
    if auth:
        for header in auth.header_lines():
            if ":" in header:
                key, value = header.split(":", 1)
                headers[key.strip()] = value.strip()
    try:
        response = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=15)
        return _filename_from_content_disposition(response.headers.get("Content-Disposition")) or _filename_from_url(response.url)
    except requests.RequestException:
        return _filename_from_url(url)


def is_cloudflare_blocked(file_path: str) -> bool:
    try:
        path = Path(file_path)
        if not path.exists() or path.stat().st_size > 100_000:
            return False
        content = path.read_text(errors="ignore").lower()
        return any(marker in content for marker in ["just a moment", "cf-browser-verification", "enable javascript", "checking your browser"])
    except Exception:
        return False


def _aria2_base(filename: str, auth: AuthConfig, extra: list[str] | None = None) -> list[str]:
    cfg = load_config()
    download_dir = Path(cfg.get("download_directory") or ".").expanduser()
    download_dir.mkdir(parents=True, exist_ok=True)
    return [
        "aria2c", "--dir", str(download_dir), "-o", filename, "-x", "8", "-s", "8",
        "--continue=true", "--min-split-size=50M", "--retry-wait=5", "--max-tries=3",
        "--auto-file-renaming=false", *(extra or []), *auth.aria2_args(),
    ]


def _run_strategy(label: str, cmd: list[str], filename: str) -> tuple[bool, bool]:
    console.print(f"[cyan]⬇  Trying {label}...[/cyan]")
    result = run_checked(cmd, capture_output=True)
    output = sanitize_text((result.stdout or "") + (result.stderr or ""))
    if result.returncode == 0 and not is_cloudflare_blocked(filename):
        log_event("download", f"{label} completed for {filename}")
        return True, False
    if output:
        log_event("error", output[-2000:])
        console.print(f"[red]{output[-800:]}[/red]")
    retryable = any(marker in output for marker in RETRYABLE_STATUS_MARKERS)
    return False, retryable or result.returncode != 0


def smart_download(url: str, filename: str, auth: AuthConfig | None = None) -> bool:
    """Try aria2 strategies, then wget fallback, delegating transfer work externally."""
    auth = auth or AuthConfig()
    strategies = [
        ("aria2 direct", _aria2_base(filename, auth) + [url]),
        ("aria2 browser User-Agent", _aria2_base(filename, auth, ["--user-agent", BROWSER_UA]) + [url]),
        ("aria2 with custom headers", _aria2_base(filename, auth) + [url]),
        ("wget fallback", ["wget", "-c", "-O", filename, *auth.wget_args(), url]),
    ]
    for label, cmd in strategies:
        ok, should_continue = _run_strategy(label, cmd, filename)
        if ok:
            return True
        Path(filename).unlink(missing_ok=True)
        if not should_continue:
            break
    return False


def collect_urls() -> list[UrlEntry]:
    console.print(Panel("[dim]Paste one or more URLs (one per line).\nPress [bold]Enter twice[/bold] when done.[/dim]", title="URL Input", border_style="cyan"))
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip() and lines:
            break
        if line.strip():
            lines.append(line.strip())
    urls = [line for line in lines if line.startswith(("http://", "https://"))]
    if not urls:
        console.print("[red]No valid URLs found.[/red]")
        return []
    auth = prompt_auth()
    entries: list[UrlEntry] = []
    for url in urls:
        detected = detect_filename(url, auth)
        console.print(f"  [dim]URL:[/dim] {sanitize_url(url)[:90]}")
        if detected:
            console.print(f"  [dim]Detected filename:[/dim] [bold]{detected}[/bold]")
            rename = questionary.text(f"  Rename? (leave empty to keep '{detected}')").ask()
            filename = rename.strip() if rename and rename.strip() else detected
        else:
            filename = questionary.text("Filename could not be detected. Enter filename:").ask()
        if filename:
            entries.append(UrlEntry(url=url, filename=filename, auth=auth))
    return entries
