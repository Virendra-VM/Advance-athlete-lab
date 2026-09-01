"""Coach provider evaluation harness.

Runs the same golden set of synthetic athletes through every requested provider,
scores the output with the rubric in ``scoring.py``, and writes a JSON report.

    # what the harness would send, no API calls, no keys needed
    python scripts/ai_eval/run_eval.py --provider rules --dry-run

    # baseline the deterministic templates (free)
    python scripts/ai_eval/run_eval.py --provider rules

    # compare real providers (needs the matching API keys in the environment)
    python scripts/ai_eval/run_eval.py --provider claude --provider openai --provider gemini

Results land in ``backend/scripts/ai_eval/results/<provider>-<timestamp>.json``
and the summary table is printed. Only synthetic athletes are used, so no real
user data ever reaches a provider from this harness.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pydantic import ValidationError  # noqa: E402

from app.ai_schemas import ChatReplyJSON, WeekPlanJSON  # noqa: E402
from app.services.ai import ProviderError, build_provider  # noqa: E402
from app.services.coach_ai import (  # noqa: E402
    CHAT_SCHEMA,
    SYSTEM_PROMPT,
    build_week_plan_prompt,
)
from app.services.coach_safety import (  # noqa: E402
    detect_red_flags,
    safety_prompt_rules,
    validate_plan,
)
from app.services.coach_templates import build_template_week, template_chat_reply  # noqa: E402
from app.services.science_kb import format_science_for_prompt  # noqa: E402
from scripts.ai_eval.golden_athletes import CHAT_PROBES, GOLDEN_ATHLETES  # noqa: E402
from scripts.ai_eval.scoring import WEIGHTS, score_case, score_chat_probe  # noqa: E402
from scripts.ai_eval.synthetic import build_case  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


_KB_STATE: dict = {"session": None, "checked": False}


def _science_session():
    """Open one session for the whole run; ``None`` means score without evidence."""
    if _KB_STATE["checked"]:
        return _KB_STATE["session"]
    _KB_STATE["checked"] = True
    try:
        from app.database import SessionLocal
        from app.services.science_kb import ensure_corpus_loaded

        db = SessionLocal()
        ensure_corpus_loaded(db)
        _KB_STATE["session"] = db
    except Exception as exc:  # noqa: BLE001 - harness must run without a database
        first_line = str(exc).strip().splitlines()[0]
        print(f"  ! science KB unavailable ({first_line}); scoring without evidence")
        _KB_STATE["session"] = None
    return _KB_STATE["session"]


def _retrieve_evidence(query: str, sports: list[str], k: int = 6) -> list[dict]:
    db = _science_session()
    if db is None:
        return []
    from app.services.science_kb import retrieve_science

    return retrieve_science(db, query, sports=sports, k=k)


def _next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def run_provider(
    provider_name: str,
    week_start: date,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    provider = None
    if provider_name != "rules" and not dry_run:
        provider = build_provider(provider_name)
        if provider is None:
            raise SystemExit(f"Unknown provider '{provider_name}'.")
        if not provider.is_configured():
            raise SystemExit(
                f"Provider '{provider_name}' has no API key configured. "
                "Set the matching *_API_KEY environment variable or use --provider rules."
            )

    athletes = GOLDEN_ATHLETES[:limit] if limit else GOLDEN_ATHLETES
    cases: list[dict] = []

    for athlete in athletes:
        case = build_case(athlete, today=week_start)
        context, safety = case["context"], case["safety"]
        goal = context["profile"]["primary_goal"]
        query = f"weekly training structure for {goal} {' '.join(case['sports'])}"
        hits = _retrieve_evidence(query, case["sports"])
        prompt = build_week_plan_prompt(context, safety, hits, week_start)

        if dry_run:
            cases.append(
                {
                    "athlete": athlete["id"],
                    "prompt_chars": len(prompt),
                    "evidence": len(hits),
                    "safety_rules": safety_prompt_rules(safety),
                }
            )
            continue

        raw: dict | None = None
        parsed: WeekPlanJSON | None = None
        error: str | None = None
        started = time.perf_counter()

        if provider is None:
            model_plan = build_template_week(context, safety, week_start)
            raw = model_plan
            try:
                parsed = WeekPlanJSON.model_validate(model_plan)
            except ValidationError as exc:
                error = f"template failed its own schema: {exc.error_count()} issue(s)"
        else:
            try:
                response = provider.generate_json(SYSTEM_PROMPT, prompt)
                raw = response.data
                parsed = WeekPlanJSON.model_validate(raw)
            except ProviderError as exc:
                error = f"provider error: {exc}"
            except ValidationError as exc:
                error = f"schema error: {exc.error_count()} issue(s)"
            except Exception as exc:  # noqa: BLE001
                error = f"unexpected error: {exc}"

        latency_ms = round((time.perf_counter() - started) * 1000)

        model_output = (
            parsed.model_dump(mode="json") if parsed is not None else (raw if isinstance(raw, dict) else {})
        )
        model_output.setdefault("week_start", week_start.isoformat())
        validation = validate_plan(dict(model_output), safety)
        scores = score_case(
            raw=raw,
            parsed=parsed,
            validated_plan=validation["plan"],
            issues=validation["issues"],
            blocked=validation["blocked"],
            athlete=athlete,
            safety=safety,
            evidence_count=len(hits),
            pre_validation_plan=model_output,
        )

        cases.append(
            {
                "athlete": athlete["id"],
                "latency_ms": latency_ms,
                "error": error,
                "blocked": validation["blocked"],
                "safety_issues": validation["issues"],
                "scores": scores,
                "plan": validation["plan"],
            }
        )
        print(
            f"  {athlete['id']:<28} {scores['total']:.3f}"
            + (f"  [{error}]" if error else "")
        )

    chat_results = []
    if not dry_run:
        probe_case = build_case(GOLDEN_ATHLETES[0], today=week_start)
        for probe in CHAT_PROBES:
            reply: dict | None = None
            red_flags = detect_red_flags(probe["message"])
            hits = _retrieve_evidence(probe["message"], probe_case["sports"], k=4)

            if provider is None:
                reply = (
                    {
                        "reply": "Stop training and get assessed by a professional.",
                        "citations": [],
                        "escalate": True,
                        "escalation_reason": ", ".join(red_flags),
                    }
                    if red_flags
                    else template_chat_reply(probe["message"], probe_case["safety"], hits)
                )
            else:
                chat_prompt = f"""ATHLETE CONTEXT
{json.dumps(probe_case['context']['profile'], indent=2, default=str)}

SAFETY RULES (hard limits)
{safety_prompt_rules(probe_case['safety'])}

RETRIEVED EVIDENCE
{format_science_for_prompt(hits)}

ATHLETE MESSAGE
{probe['message']}

TASK
Answer as their coach. Reply with JSON matching exactly this shape:
{CHAT_SCHEMA}"""
                try:
                    response = provider.generate_json(SYSTEM_PROMPT, chat_prompt)
                    reply = ChatReplyJSON.model_validate(response.data).model_dump(mode="json")
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! chat probe {probe['id']} failed: {exc}")

            score = score_chat_probe(reply, probe["expect_escalation"])
            chat_results.append({"probe": probe["id"], **score, "reply": reply})
            print(f"  chat:{probe['id']:<23} {score['total']:.3f}")

    scored = [case for case in cases if "scores" in case]
    dimension_means = {}
    if scored:
        for key in WEIGHTS:
            dimension_means[key] = round(
                sum(case["scores"]["dimensions"][key]["score"] for case in scored) / len(scored), 3
            )

    return {
        "provider": provider_name,
        "model": getattr(provider, "model", "deterministic-template"),
        "week_start": week_start.isoformat(),
        "dry_run": dry_run,
        "athlete_count": len(cases),
        "overall": round(sum(case["scores"]["total"] for case in scored) / len(scored), 3)
        if scored
        else None,
        "dimension_means": dimension_means,
        "chat_safety": round(
            sum(result["total"] for result in chat_results) / len(chat_results), 3
        )
        if chat_results
        else None,
        "blocked_count": sum(1 for case in scored if case["blocked"]),
        "error_count": sum(1 for case in scored if case.get("error")),
        "median_latency_ms": (
            sorted(case["latency_ms"] for case in scored)[len(scored) // 2] if scored else None
        ),
        "cases": cases,
        "chat_probes": chat_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate coach providers on synthetic athletes.")
    parser.add_argument(
        "--provider",
        action="append",
        default=None,
        help="rules | claude | openai | gemini (repeatable)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N athletes")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build prompts and print sizes without calling any provider",
    )
    parser.add_argument("--out", default=None, help="Write the report to this path")
    args = parser.parse_args()

    providers = args.provider or ["rules"]
    week_start = _next_monday(date.today())
    reports = []

    for name in providers:
        print(f"\n== {name} ==")
        report = run_provider(name, week_start, dry_run=args.dry_run, limit=args.limit)
        reports.append(report)
        if not args.dry_run:
            print(
                f"  overall={report['overall']} chat_safety={report['chat_safety']} "
                f"blocked={report['blocked_count']} errors={report['error_count']}"
            )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"eval-{stamp}.json"
    out_path.write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")

    if not args.dry_run:
        print("\nprovider              overall  " + "  ".join(f"{key[:6]:>6}" for key in WEIGHTS))
        for report in reports:
            means = report["dimension_means"]
            print(
                f"{report['provider']:<20} {report['overall'] or 0:>7.3f}  "
                + "  ".join(f"{means.get(key, 0):>6.3f}" for key in WEIGHTS)
            )
    print(f"\nreport → {out_path}")


if __name__ == "__main__":
    main()
