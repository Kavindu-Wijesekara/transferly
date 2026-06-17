"""Upload and streaming helpers."""

from __future__ import annotations

import subprocess

from rich.console import Console

from .downloads import CURL_CFFI_AVAILABLE, cf_requests, run, run_shell

console = Console()


def upload_file(file: str, remote: str, folder: str) -> bool:
    console.print(f"[green]⬆  Uploading [bold]{file}[/bold] → {remote}:{folder}/[/green]")
    dest = f"{remote}:{folder}/{file}"
    return run([
        "rclone", "copyto", file, dest,
        "--drive-chunk-size", "128M",
        "--transfers", "4",
        "--checkers", "8",
        "-P",
    ])


def stream_upload(url: str, filename: str, remote: str, folder: str) -> bool:
    """Stream URL directly to cloud using curl pipe → rclone rcat."""
    dest = f"{remote}:{folder}/{filename}"
    console.print(f"[cyan]⚡ Streaming [bold]{filename}[/bold] → {dest}[/cyan]")

    curl_cmd = (
        f'curl -L --retry 3 --retry-wait 5 -A "Mozilla/5.0" '
        f'--fail --silent --show-error "{url}" | rclone rcat "{dest}" -P'
    )
    if run_shell(curl_cmd):
        return True

    if CURL_CFFI_AVAILABLE:
        console.print("[yellow]curl stream failed. Trying curl_cffi stream fallback...[/yellow]")
        try:
            with cf_requests.Session(impersonate="chrome120") as session:  # type: ignore[union-attr]
                r = session.get(url, stream=True, timeout=30)
                r.raise_for_status()
                rclone_proc = subprocess.Popen(["rclone", "rcat", dest, "-P"], stdin=subprocess.PIPE)
                assert rclone_proc.stdin is not None
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        rclone_proc.stdin.write(chunk)
                rclone_proc.stdin.close()
                rclone_proc.wait()
                return rclone_proc.returncode == 0
        except Exception as e:
            console.print(f"[red]Stream fallback failed: {e}[/red]")

    return False
