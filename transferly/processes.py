"""Supervised subprocess helpers with graceful cancellation."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from rich.console import Console

console = Console()


@dataclass
class ProcessSupervisor:
    """Track active child processes and terminate them on Ctrl+C."""

    processes: list[subprocess.Popen] = field(default_factory=list)

    def popen(self, args: Sequence[str], **kwargs) -> subprocess.Popen:
        proc = subprocess.Popen(list(args), **kwargs)
        self.processes.append(proc)
        return proc

    def run(self, args: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
        proc = self.popen(args, **kwargs)
        try:
            stdout, stderr = proc.communicate()
        except KeyboardInterrupt:
            self.cancel()
            raise
        return subprocess.CompletedProcess(args=list(args), returncode=proc.returncode, stdout=stdout, stderr=stderr)

    def cancel(self) -> None:
        for proc in self.processes:
            if proc.poll() is None:
                proc.terminate()
        deadline = time.time() + 5
        for proc in self.processes:
            while proc.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if proc.poll() is None:
                proc.kill()
        console.print("\n[yellow]Transfer cancelled.[/yellow]")


SUPERVISOR = ProcessSupervisor()


def run_checked(args: Sequence[str], *, capture_output: bool = False, text: bool = True) -> subprocess.CompletedProcess:
    """Run a command through the global supervisor."""
    kwargs = {"text": text}
    if capture_output:
        kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.PIPE})
    return SUPERVISOR.run(args, **kwargs)
