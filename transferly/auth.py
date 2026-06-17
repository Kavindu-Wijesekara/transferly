"""Authentication helpers for future Transferly workflows."""

from __future__ import annotations


def authorization_headers(token: str | None = None, headers: dict[str, str] | None = None) -> dict[str, str]:
    """Build optional HTTP authorization/custom headers."""
    result = dict(headers or {})
    if token:
        result["Authorization"] = f"Bearer {token}"
    return result
