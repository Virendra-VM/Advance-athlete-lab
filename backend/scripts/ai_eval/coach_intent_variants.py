"""Generate 200+ grammatical phrasing variants per core coach intent."""

from __future__ import annotations

import itertools
import re

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
from app.services.coach_skills import (
    SKILL_ADJUST_DAY,
    SKILL_CLINICAL,
    SKILL_EXPLAIN_METRIC,
    SKILL_GENERAL_CHAT,
    SKILL_MONTH_DEBRIEF,
    SKILL_OFF_TOPIC,
    SKILL_REBUILD_WEEK,
    SKILL_REVIEW_SESSION,
    SKILL_WEEK_DEBRIEF,
    SKILL_YEAR_DEBRIEF,
)

_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS.sub(" ", (text or "").strip())


def _cases_from_messages(category, skill, intent, messages, *, target=220):
    from scripts.ai_eval.coach_golden_bank import GoldenRoutingCase

    seen = set()
    out = []
    for message in messages:
        text = _clean(message)
        key = text.lower()
        if len(text) < 8 or key in seen:
            continue
        seen.add(key)
        out.append(
            GoldenRoutingCase(
                case_id=f"{category}_{len(out) + 1:03d}",
                message=text,
                category=category,
                expected_skill=skill,
                expected_intent=intent,
                acceptable_skills=(skill,),
                strict_intent=True,
            )
        )
        if len(out) >= target:
            break
    return out


def _combine(questions, requests, tails, openers):
    messages = []
    for question in questions:
        for opener, tail in itertools.product(openers, tails):
            messages.append(f"{opener}{question}{tail}")
    for request in requests:
        for opener in ["Can you ", "Please ", "Coach, please ", "Hey coach, "]:
            for tail in tails:
                messages.append(f"{opener}{request}{tail}")
    return messages


def build_intent_variant_bank() -> list:
    tails = ["", " please", " coach", " — be honest", " when you have a second"]
    openers = ["", "Hey, ", "Quick one: ", "Need a read: ", "Honestly, "]

    week = _cases_from_messages(
        "week_debrief",
        SKILL_WEEK_DEBRIEF,
        WEEK_REVIEW,
        _combine(
            [
                "How did I do this week?",
                "How was last week?",
                "How did training go this week?",
                "How much have I improved over the last 7 days?",
                "How was my week overall?",
            ],
            [
                "analyse my last week and tell me how I did",
                "analyze last week",
                "recap last week",
                "review my week",
                "grade my week",
                "summarize my week",
                "give me a weekly debrief",
                "look at the past seven days of training",
            ],
            tails,
            openers,
        )
        + [
            "Can you analyse my last week and tell me how did i do in that week.",
            "Analyse my week, let's see how much i have improved",
        ],
    )
    month = _cases_from_messages(
        "month_debrief",
        SKILL_MONTH_DEBRIEF,
        MONTH_REVIEW,
        _combine(
            [
                "How did I do this month?",
                "How was last month?",
                "How much have I improved over the last 30 days?",
                "How did the last 4 weeks go?",
                "Am I fitter than I was 30 days ago?",
            ],
            [
                "analyse my last month",
                "recap last month",
                "review my month",
                "grade my month",
                "summarize my month",
                "give me a monthly recap",
                "look at the last 4 weeks of training",
            ],
            tails,
            openers,
        ),
    )
    year = _cases_from_messages(
        "year_debrief",
        SKILL_YEAR_DEBRIEF,
        YEAR_REVIEW,
        _combine(
            [
                "How did I do this year?",
                "How was last year?",
                "How much have I improved over the last 12 months?",
                "How has this season gone?",
                "Am I fitter than last year?",
            ],
            [
                "analyse my year of training",
                "recap last year",
                "review my year",
                "grade my year",
                "summarize this year",
                "give me a yearly recap",
                "look at the last 12 months",
                "give me a year in review",
            ],
            tails,
            openers,
        ),
    )
    session = _cases_from_messages(
        "review_session",
        SKILL_REVIEW_SESSION,
        WORKOUT_AUDIT,
        _combine(
            [
                "How was today's session?",
                "How was today's ride?",
                "How was today's run?",
                "How did I do today?",
                "How was yoga?",
                "How was the lift?",
            ],
            [
                "analyse this ride",
                "analyze this run",
                "autopsy yesterday's session",
                "match my workout to the file",
                "look at this trainer file",
                "break down this morning's intervals",
            ],
            tails,
            openers,
        )
        + ["you got it wrong coach, look at the laps", "lap by lap please on this ride"],
    )
    schedule = _cases_from_messages(
        "rebuild_week",
        SKILL_REBUILD_WEEK,
        SCHEDULE_UPDATE,
        _combine(
            [
                "How should I adjust this week?",
            ],
            [
                "plan my week",
                "build my week",
                "adjust this week's plan",
                "update my schedule for this week",
                "rewrite my week",
                "build a recovery week",
                "plan the rest of this week",
                "revise my week",
                "change Friday intervals this week",
            ],
            tails,
            openers,
        ),
    )
    day = _cases_from_messages(
        "adjust_day",
        SKILL_ADJUST_DAY,
        DAY_ADJUST,
        _combine(
            [
                "HRV is low, should I still do intervals today?",
                "Readiness is bad, how should I train today?",
                "ACWR is high, skip today's workout?",
                "Stressed this morning, can I still train?",
                "Poor sleep, swap today to easy?",
            ],
            [
                "downgrade today only",
                "skip today's quality, sleep was terrible",
                "adjust today, my HRV dropped",
                "skip today I slept badly",
                "change today only because readiness is low",
            ],
            tails,
            openers,
        ),
    )
    science = _cases_from_messages(
        "explain_metric",
        SKILL_EXPLAIN_METRIC,
        SCIENCE_LOOKUP,
        _combine(
            [
                "What is ACWR?",
                "What is FTP?",
                "What is HRV?",
                "What is LTHR?",
                "What is TSS?",
                "What is zone 2?",
                "How does ACWR work?",
                "Why does ACWR matter?",
                "Why is my HRV low?",
                "What does training load ratio mean?",
            ],
            [
                "explain polarized training",
                "explain lactate threshold",
                "explain carbohydrate periodization",
                "explain heat acclimation",
            ],
            tails,
            openers,
        ),
    )
    general = _cases_from_messages(
        "general_chat",
        SKILL_GENERAL_CHAT,
        GENERAL_CHAT,
        _combine(
            [
                "How easy should easy sessions feel?",
                "How should I fuel before a long run?",
                "How do I build consistency?",
                "How should I breathe on easy runs?",
                "How long should my long run be?",
                "How hard should threshold feel?",
            ],
            [
                "give tips for pacing a half marathon",
                "give advice for first-time marathon training",
                "suggest a good warm-up before intervals",
                "suggest how to handle heat in summer training",
            ],
            tails,
            openers,
        ),
    )
    clinical = _cases_from_messages(
        "clinical",
        SKILL_CLINICAL,
        CLINICAL_VETO,
        _combine(
            [
                "Sharp pain in my knee when I run",
                "Stabbing pain in my hip",
                "Chest pain during intervals",
                "Sharp shin pain — should I run?",
                "I think I tore my calf",
                "Painful pop in my knee",
                "Numbness in my foot after long runs",
                "My back spasms when I deadlift",
            ],
            [
                "look at this sharp pain in my Achilles",
                "help with stabbing pain in my hamstring",
                "check this sharp shoulder pain on the bike",
            ],
            tails,
            openers,
        ),
    )
    off_topic = _cases_from_messages(
        "off_topic",
        SKILL_OFF_TOPIC,
        OFF_TOPIC,
        _combine(
            [
                "What's the stock price of Apple?",
                "Which crypto should I buy?",
                "Who won the election?",
                "What's the capital of France?",
                "How do I fix my WiFi?",
            ],
            [
                "write me a Python script",
                "help with my taxes",
                "book me a flight",
                "recommend a restaurant nearby",
                "do my homework for me",
                "give me a recipe for lasagna",
                "tell me a joke about cats",
            ],
            tails,
            openers,
        ),
    )
    return week + month + year + session + schedule + day + science + general + clinical + off_topic
