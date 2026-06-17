"""Download helpers and URL input flows."""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import questionary
import requests as std_requests
from rich import print
from rich.console import Console
from rich.panel import Panel

if importlib.util.find_spec("curl_cffi") is not None:
    cf_requests = importlib.import_module("curl_cffi.requests")
    CURL_CFFI_AVAILABLE = True
else:
    cf_requests = None
    CURL_CFFI_AVAILABLE = False

console = Console()


def run(cmd: list[str], silent: bool = False) -> bool:
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


def run_output(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip()


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


def download_aria2c(url: str, filename: str) -> bool:
    """Primary downloader using aria2c."""
    console.print("[cyan]⬇  Trying aria2c...[/cyan]")
    success = run([
        "aria2c", "-o", filename, "-x", "4", "-s", "4", "--min-split-size=50M",
        "--retry-wait=5", "--max-tries=3", "--auto-file-renaming=false", url,
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
        with cf_requests.Session(impersonate="chrome120") as session:  # type: ignore[name-defined]
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


def collect_urls() -> list[dict[str, str]]:
    """Collect one or more URLs via multiline paste."""
    console.print(Panel(
        "[dim]Paste one or more URLs (one per line).\nPress [bold]Enter twice[/bold] (blank line) when done.[/dim]",
        title="URL Input",
        border_style="cyan",
    ))

    lines: list[str] = []
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

    urls = [line for line in lines if line.startswith("http")]
    if not urls:
        console.print("[red]No valid URLs found.[/red]")
        return []

    console.print(f"\n[green]Found {len(urls)} URL(s)[/green]\n")
    entries: list[dict[str, str]] = []
    for url in urls:
        detected = detect_filename(url)
        console.print(f"  [dim]URL:[/dim] {url[:70]}{'...' if len(url) > 70 else ''}")
        console.print(f"  [dim]Detected filename:[/dim] [bold]{detected}[/bold]")
        rename = questionary.text(f"  Rename? (leave empty to keep '{detected}')").ask()
        filename = rename.strip() if rename and rename.strip() else detected
        entries.append({"url": url, "filename": filename})
        console.print()

    return entries
