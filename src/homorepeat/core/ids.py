"""Deterministic identifier helpers."""

from __future__ import annotations

import hashlib
import re


_WHITESPACE_RE = re.compile(r"\s+")


def stable_id(prefix: str, *parts: object, length: int = 12) -> str:
    """Build a stable short identifier from normalized input parts."""

    normalized_parts = [str(part).strip() for part in parts]
    digest = hashlib.blake2b(
        "||".join(normalized_parts).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    return f"{prefix}_{digest[:length]}"


def text_id(*parts: object) -> str:
    """Build a stable text identifier from source-backed parts."""

    normalized_parts: list[str] = []
    for part in parts:
        text = _WHITESPACE_RE.sub("_", str(part).strip())
        if text:
            normalized_parts.append(text)
    if not normalized_parts:
        raise ValueError("text_id requires at least one non-empty part")
    return "::".join(normalized_parts)


def batch_id(index: int) -> str:
    """Build a deterministic operational batch identifier."""

    return f"batch_{index:04d}"
