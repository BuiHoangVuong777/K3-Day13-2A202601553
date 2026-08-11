from __future__ import annotations

import hashlib
import re
from typing import Any


PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<![A-Za-z0-9_])(?:\+84|0)(?:[ .-]?\d){9}(?![A-Za-z0-9_])",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",

    # Security credentials
    "bearer_token": r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
    "secret_assignment": (
        r"(?i)\b"
        r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
        r"auth[_-]?token|password|client[_-]?secret)"
        r"\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{8,}['\"]?"
    ),
}


SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "auth_token",
    "authorization",
    "password",
    "secret",
    "client_secret",
}


def scrub_text(text: str) -> str:
    """Redact PII and secrets inside a string."""
    safe = text

    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(
            pattern,
            f"[REDACTED_{name.upper()}]",
            safe,
        )

    return safe


def scrub_value(value: Any, key: str | None = None) -> Any:
    """Recursively scrub PII/secrets from structured log data."""

    normalized_key = key.lower().replace("-", "_") if key else None

    # Credential fields must never be written as raw values.
    if normalized_key in SENSITIVE_KEYS:
        return "[REDACTED_SECRET]"

    if isinstance(value, str):
        return scrub_text(value)

    if isinstance(value, dict):
        return {
            k: scrub_value(v, str(k))
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [
            scrub_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            scrub_value(item)
            for item in value
        )

    return value


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(
        user_id.encode("utf-8")
    ).hexdigest()[:12]