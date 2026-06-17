"""Security and redaction helpers."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_HEADER_RE = re.compile(r"(?i)(authorization|cookie|set-cookie)\s*:\s*[^\n\r]+")
BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
SENSITIVE_QUERY_KEYS = {"token", "access_token", "auth", "authorization", "signature", "sig", "key", "apikey", "api_key"}


def sanitize_text(value: object) -> str:
    """Redact tokens, cookies, and common signed URL values from text."""
    text = str(value)
    text = SECRET_HEADER_RE.sub(lambda m: f"{m.group(1)}: [REDACTED]", text)
    text = BEARER_RE.sub("Bearer [REDACTED]", text)
    return text


def sanitize_url(url: str) -> str:
    """Redact sensitive query parameters while preserving enough URL context for history."""
    parts = urlsplit(url)
    safe_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        safe_query.append((key, "[REDACTED]" if key.lower() in SENSITIVE_QUERY_KEYS else value))
    return sanitize_text(urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_query), parts.fragment)))
