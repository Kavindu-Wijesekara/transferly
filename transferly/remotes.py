"""Rclone remote browsing helpers."""

from __future__ import annotations

import questionary

from .config import load_config, save_config
from .downloads import run, run_output


def list_remotes() -> list[str]:
    out = run_output(["rclone", "listremotes"])
    return [remote.replace(":", "") for remote in out.splitlines()]


def list_dirs(remote: str, path: str = "") -> list[str]:
    target = f"{remote}:{path}" if path else f"{remote}:"
    out = run_output(["rclone", "lsf", target, "--dirs-only"])
    return [directory.strip("/") for directory in out.splitlines()]


def browse_remote(remote: str) -> str | None:
    current = ""
    cfg = load_config()
    last_folder = cfg.get("last_folder", {}).get(remote, "")
    if last_folder and questionary.confirm(f"Use last folder? [{remote}:{last_folder}]").ask():
        return last_folder
    while True:
        dirs = list_dirs(remote, current)
        choices = ([".. (back)"] if current else []) + dirs + ["[Create folder]", "[Select this folder]", "[Cancel]"]
        choice = questionary.select(f"📁 {remote}:{current or '/'}", choices=choices).ask()
        if choice in (None, "[Cancel]"):
            return None
        if choice == ".. (back)":
            current = "/".join(current.split("/")[:-1])
        elif choice == "[Create folder]":
            name = questionary.text("Folder name:").ask()
            if name:
                run(["rclone", "mkdir", f"{remote}:{current}/{name}"])
                current = f"{current}/{name}".strip("/")
        elif choice == "[Select this folder]":
            cfg.setdefault("last_folder", {})[remote] = current
            save_config(cfg)
            return current
        else:
            current = f"{current}/{choice}".strip("/")
