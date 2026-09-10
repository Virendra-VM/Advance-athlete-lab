"""Phase D — coach chat stream helpers."""

from __future__ import annotations

import json

from app.services.coach_stream import (
    delta_event,
    done_event,
    status_event,
    stream_reply_deltas,
)


def test_stream_reply_deltas_cover_full_text():
    text = "Keep today easy and sleep well tonight."
    chunks = list(stream_reply_deltas(text, chunk_words=2))
    assert "".join(chunks) == text


def test_status_event_is_ndjson():
    line = status_event("Reading your training…")
    payload = json.loads(line.strip())
    assert payload["type"] == "status"
    assert payload["text"]


def test_done_event_wraps_payload():
    line = done_event({"provider": "rules", "reply": {"reply": "Hi"}})
    payload = json.loads(line.strip())
    assert payload["type"] == "done"
    assert payload["payload"]["provider"] == "rules"


def test_delta_event_chunks():
    line = delta_event("Hello ")
    payload = json.loads(line.strip())
    assert payload == {"type": "delta", "text": "Hello "}
