"""Phase D — NDJSON streaming events for coach chat."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

STREAM_STATUSES = (
    "Reading your training…",
    "Checking sleep and load…",
    "Running coach tools…",
    "Writing your reply…",
)


def stream_reply_deltas(text: str, *, chunk_words: int = 3) -> Iterator[str]:
    """Yield reply text in small word groups for perceived streaming."""
    words = re.split(r"(\s+)", text or "")
    buffer: list[str] = []
    count = 0
    for token in words:
        buffer.append(token)
        if token.strip():
            count += 1
        if count >= chunk_words:
            yield "".join(buffer)
            buffer = []
            count = 0
    if buffer:
        yield "".join(buffer)


def status_event(text: str) -> str:
    return json.dumps({"type": "status", "text": text}, ensure_ascii=False) + "\n"


def delta_event(text: str) -> str:
    return json.dumps({"type": "delta", "text": text}, ensure_ascii=False) + "\n"


def done_event(payload: dict[str, Any]) -> str:
    return json.dumps({"type": "done", "payload": payload}, ensure_ascii=False, default=str) + "\n"


def error_event(message: str) -> str:
    return json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n"
