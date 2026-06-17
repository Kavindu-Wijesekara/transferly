"""Upload and aria2/rclone streaming helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

from .auth import AuthConfig
from .downloads import BROWSER_UA
from .logging import log_event
from .processes import SUPERVISOR, run_checked

console = Console()


def _join_remote(remote: str, folder: str, filename: str) -> str:
    clean = folder.strip("/")
    return f"{remote}:{clean}/{filename}" if clean else f"{remote}:{filename}"


def upload_file(file: str, remote: str, folder: str, rename: str | None = None) -> bool:
    local_path = Path(file).expanduser()
    remote_name = rename or local_path.name
    dest = _join_remote(remote, folder, remote_name)
    console.print(f"[green]⬆  Uploading [bold]{local_path}[/bold] → {dest}[/green]")
    result = run_checked([
        "rclone", "copyto", str(local_path), dest,
        "--drive-chunk-size", "128M", "--transfers", "4", "--checkers", "8", "-P",
    ])
    ok = result.returncode == 0
    log_event("upload", f"upload {local_path} to {dest}: {ok}")
    return ok


def stream_upload(url: str, filename: str, remote: str, folder: str, auth: AuthConfig | None = None) -> bool:
    """Stream URL to cloud using supervised aria2 stdout -> rclone rcat orchestration."""
    auth = auth or AuthConfig()
    dest = _join_remote(remote, folder, filename)
    console.print(f"[cyan]⚡ Streaming [bold]{filename}[/bold] → {dest}[/cyan]")
    aria2_cmd = [
        "aria2c", "--quiet=true", "--summary-interval=0", "--console-log-level=error",
        "--allow-overwrite=true", "--auto-file-renaming=false", "--user-agent", BROWSER_UA,
        "--out", "-", *auth.aria2_args(), url,
    ]
    try:
        aria2_proc = SUPERVISOR.popen(aria2_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert aria2_proc.stdout is not None
        rclone_proc = SUPERVISOR.popen(["rclone", "rcat", dest, "-P"], stdin=aria2_proc.stdout)
        aria2_proc.stdout.close()
        rclone_return = rclone_proc.wait()
        _, aria2_stderr = aria2_proc.communicate()
        if aria2_stderr:
            message = aria2_stderr.decode(errors="ignore")[-800:]
            log_event("error", message)
            console.print(f"[red]{message}[/red]")
        ok = aria2_proc.returncode == 0 and rclone_return == 0
        log_event("stream", f"stream to {dest}: {ok}")
        return ok
    except KeyboardInterrupt:
        SUPERVISOR.cancel()
        raise
