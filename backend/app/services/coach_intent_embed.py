"""Hashed n-gram embeddings for long-tail coach intent routing.

No extra ML dependency: MD5-hashed character trigrams + word unigrams into a
fixed vector, then cosine similarity against intent centroids. Used when
structural keyword scores are weak or default to GENERAL_CHAT.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from functools import lru_cache

from app.services.coach_intent import (
    CLINICAL_VETO,
    DAY_ADJUST,
    GENERAL_CHAT,
    MONTH_REVIEW,
    OFF_TOPIC,
    SCHEDULE_UPDATE,
    SCIENCE_LOOKUP,
    WEEK_REVIEW,
    WORKOUT_AUDIT,
    YEAR_REVIEW,
)

DIM = 384
MIN_SIMILARITY = 0.28
MIN_MARGIN = 0.035

_TOKEN_RE = re.compile(r"[a-z0-9']+")
_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip().lower())


def _tokens(text: str) -> list[str]:
    compact = _normalize(text)
    words = _TOKEN_RE.findall(compact)
    collapsed = compact.replace(" ", "")
    grams = [collapsed[i : i + 3] for i in range(max(0, len(collapsed) - 2))]
    return words + grams


def _bucket(token: str) -> tuple[int, float]:
    digest = hashlib.md5(token.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:4], "little") % DIM
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    weight = 2.0 if "'" in token or token.isalpha() and len(token) > 2 else 1.0
    return idx, sign * weight


def embed_text(text: str) -> tuple[float, ...]:
    vec = [0.0] * DIM
    for token in _tokens(text):
        idx, weight = _bucket(token)
        vec[idx] += weight
    norm = math.sqrt(sum(value * value for value in vec))
    if norm <= 0:
        return tuple(vec)
    return tuple(value / norm for value in vec)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return float(sum(a * b for a, b in zip(left, right)))


EXEMPLARS: dict[str, tuple[str, ...]] = {
    WORKOUT_AUDIT: (
        "how was today's session",
        "analyse this ride lap by lap",
        "how did i do on this morning's run",
        "autopsy yesterday's workout",
        "how was this swim",
        "match my workout to the prescribed watts",
        "you got it wrong coach look at the laps",
        "how was yoga today",
        "tell me about this trainer session",
        "analyze today's bike file",
        "how did i perform on the intervals",
        "break down this afternoon's run",
    ),
    WEEK_REVIEW: (
        "how did i do this week",
        "analyse my last week and tell me how i did",
        "how much have i improved over the last 7 days",
        "recap last week",
        "grade my week",
        "summarize my week",
        "weekly debrief please",
        "look at the past seven days of training",
        "how was last week overall",
        "done with the week debrief me",
        "how's my training been this past week",
        "what did last week's load actually look like",
    ),
    MONTH_REVIEW: (
        "how did i do this month",
        "analyse my last month",
        "how much have i improved over the last 30 days",
        "monthly recap please",
        "grade my month of training",
        "summarize the past month",
        "look at my last 4 weeks",
        "how was last month overall",
        "am i fitter than i was 30 days ago",
        "review my training this month",
        "how's the last month of training gone",
        "progress check for the past 30 days",
    ),
    YEAR_REVIEW: (
        "how did i do this year",
        "analyse my year of training",
        "how much have i improved over the last 12 months",
        "yearly recap please",
        "grade my season",
        "summarize this year of training",
        "look at my last 12 months",
        "how was last year overall",
        "year in review for my training",
        "am i fitter than last year",
        "review my season so far",
        "how's my year of training gone",
    ),
    SCHEDULE_UPDATE: (
        "plan my week",
        "adjust this week's schedule",
        "build a recovery week for me",
        "update my remaining week",
        "rewrite my week around a race",
        "change friday intervals to easy",
        "what should i do this week going forward",
        "rebuild the calendar for this week",
        "swap saturday long with sunday",
        "schedule update drop quality",
        "plan the rest of this week",
        "build my training week",
    ),
    DAY_ADJUST: (
        "hrv is low should i still do intervals today",
        "skip today's quality sleep was terrible",
        "readiness is bad how should i train today",
        "acwr is high skip today's workout",
        "stressed this morning can i still train",
        "downgrade today only",
        "should i still do the threshold session today",
        "poor sleep swap today to easy",
        "today only change because hrv dropped",
        "can i still train with high stress this morning",
        "adjust today my readiness is low",
        "skip today i slept badly",
    ),
    SCIENCE_LOOKUP: (
        "what is acwr",
        "explain hrv in plain language",
        "how does polarized training work",
        "what is ftp on the bike",
        "why does acwr matter",
        "latest research on heat acclimation",
        "what is lactate threshold",
        "explain zone 2",
        "what does training load ratio mean",
        "how does carbohydrate periodization work",
        "what is tss",
        "why is my hrv low",
    ),
    GENERAL_CHAT: (
        "how easy should easy sessions feel",
        "tips for pacing a half marathon",
        "how should i fuel before a long run",
        "how do i build consistency",
        "what's a good warm-up before intervals",
        "advice for first-time marathon training",
        "how should i breathe on easy runs",
        "should i cross-train on rest days",
        "how do i handle heat in summer training",
        "what cadence should i aim for",
        "how long should my long run be",
        "best way to recover after a hard session",
    ),
    CLINICAL_VETO: (
        "sharp pain in my knee when i run",
        "i think i tore my calf",
        "stabbing pain in my hip",
        "chest pain during intervals",
        "achilles tendon hurts after yesterday",
        "diagnosed with a stress fracture",
        "numbness in my foot after long runs",
        "painful pop in my knee",
        "sharp shin pain should i run",
        "acl recovery when can i run",
        "my back spasms when i deadlift",
        "doctor said plantar fasciitis can i train",
    ),
    OFF_TOPIC: (
        "what's the weather tomorrow",
        "write me a python script",
        "who won the election",
        "recommend a restaurant nearby",
        "help with my taxes",
        "what's the capital of france",
        "tell me a joke about cats",
        "book me a flight",
        "how do i fix my wifi",
        "what's the stock price of apple",
        "which crypto should i buy",
        "do my homework for me",
    ),
}


@dataclass(frozen=True)
class EmbedDecision:
    intent: str
    confidence: float
    source: str
    similarity: float
    runner_up: str | None
    margin: float


@lru_cache(maxsize=1)
def _centroids() -> dict[str, tuple[float, ...]]:
    out: dict[str, tuple[float, ...]] = {}
    for intent, phrases in EXEMPLARS.items():
        acc = [0.0] * DIM
        for phrase in phrases:
            vec = embed_text(phrase)
            for i, value in enumerate(vec):
                acc[i] += value
        n = float(len(phrases) or 1)
        mean = [value / n for value in acc]
        norm = math.sqrt(sum(value * value for value in mean)) or 1.0
        out[intent] = tuple(value / norm for value in mean)
    return out


def classify_with_embeddings(message: str) -> EmbedDecision | None:
    text = _normalize(message)
    if not text:
        return None
    retro = bool(
        re.search(
            r"\b(how did i do|how was|how's my|recap|review|debrief|grade|summarize|summarise|"
            r"analyse|analyze|improved|improvement|progress|fitter)\b",
            text,
        )
    )
    if retro and re.search(
        r"\b(last 7 days|past 7 days|last seven days|past week|this week|last week)\b",
        text,
    ):
        if re.search(r"\b(month|30 days|12 months|year|season)\b", text) is None:
            forced = WEEK_REVIEW
        else:
            forced = None
    elif retro and re.search(
        r"\b(last 30 days|past 30 days|last 4 weeks|this month|last month|30 days ago)\b",
        text,
    ):
        forced = MONTH_REVIEW
    elif retro and re.search(
        r"\b(last 12 months|this year|last year|this season|year in review)\b",
        text,
    ):
        forced = YEAR_REVIEW
    else:
        forced = None

    vector = embed_text(text)
    ranked: list[tuple[str, float]] = []
    for intent, centroid in _centroids().items():
        ranked.append((intent, cosine(vector, centroid)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    best_intent, best_sim = ranked[0]
    second_intent, second_sim = ranked[1] if len(ranked) > 1 else (None, 0.0)
    if forced:
        best_intent = forced
        best_sim = max(best_sim, MIN_SIMILARITY + 0.05)
        margin = max(MIN_MARGIN, best_sim - second_sim)
    else:
        margin = best_sim - second_sim
        if best_sim < MIN_SIMILARITY or margin < MIN_MARGIN:
            return None
    confidence = min(0.88, 0.5 + best_sim * 0.4 + max(margin, 0.05))
    return EmbedDecision(
        intent=best_intent,
        confidence=round(confidence, 3),
        source="embedding",
        similarity=round(best_sim, 3),
        runner_up=second_intent,
        margin=round(margin, 3),
    )
