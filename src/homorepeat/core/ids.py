"""Deterministic identifier helpers."""

from __future__ import annotations

import hashlib


def stable_id(prefix: str, *parts: object, length: int = 12) -> str:
    """Build a stable short identifier from normalized input parts."""

    normalized_parts = [str(part).strip() for part in parts]
    digest = hashlib.blake2b(
        "||".join(normalized_parts).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    return f"{prefix}_{digest[:length]}"


def batch_id(index: int) -> str:
    """Build a deterministic operational batch identifier."""

    return f"batch_{index:04d}"
