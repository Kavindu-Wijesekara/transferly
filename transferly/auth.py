"""Reusable authentication prompts and command argument builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import questionary


@dataclass
class AuthConfig:
    kind: str = "none"
    bearer_token: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    cookie_file: Path | None = None

    def header_lines(self) -> list[str]:
        lines = [f"{key}: {value}" for key, value in self.headers.items()]
        if self.bearer_token:
            lines.append(f"Authorization: Bearer {self.bearer_token}")
        return lines

    def aria2_args(self) -> list[str]:
        args: list[str] = []
        for header in self.header_lines():
            args.extend(["--header", header])
        if self.cookie_file:
            args.extend(["--load-cookies", str(self.cookie_file)])
        return args

    def wget_args(self) -> list[str]:
        args: list[str] = []
        for header in self.header_lines():
            args.extend(["--header", header])
        if self.cookie_file:
            args.extend(["--load-cookies", str(self.cookie_file)])
        return args


def prompt_auth() -> AuthConfig:
    choice = questionary.select(
        "Authentication",
        choices=["No Authentication", "Bearer Token", "Custom Headers", "Cookie File"],
        default="No Authentication",
    ).ask()

    if choice == "Bearer Token":
        token = questionary.password("Bearer token:").ask()
        return AuthConfig(kind="bearer", bearer_token=token or None)

    if choice == "Custom Headers":
        headers: dict[str, str] = {}
        while True:
            line = questionary.text("Header (Name: value, blank when done):").ask()
            if not line:
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
        return AuthConfig(kind="headers", headers=headers)

    if choice == "Cookie File":
        cookie_file = questionary.path("Netscape cookie file:").ask()
        return AuthConfig(kind="cookies", cookie_file=Path(cookie_file).expanduser() if cookie_file else None)

    return AuthConfig()
