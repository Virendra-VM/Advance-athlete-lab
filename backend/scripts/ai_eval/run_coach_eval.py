"""Phase 7 — coach conversation quality eval harness.

Mechanical scoring (no LLM judge) for diversity, intent adherence,
plain-language readability, and athlete-panel readability proxy.

    # inspect cases only
    python scripts/ai_eval/run_coach_eval.py --dry-run

    # score deterministic template baseline (free, no API keys)
    python scripts/ai_eval/run_coach_eval.py

    # write JSON report
    python scripts/ai_eval/run_coach_eval.py --output results/coach-eval.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.coach_reply_eval import PHASE7_WEIGHTS, score_coach_reply  # noqa: E402
from scripts.ai_eval.coach_conversation_cases import COACH_CONVERSATION_CASES  # noqa: E402
from scripts.ai_eval.coach_reply_generator import generate_deterministic_reply  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def run_eval(*, dry_run: bool = False) -> dict:
    cases_out: list[dict] = []
    for case in COACH_CONVERSATION_CASES:
        entry: dict = {
            "case_id": case.case_id,
            "message": case.message,
            "description": case.description,
            "expectation": {
                "schedule_mode": case.expectation.schedule_mode,
                "require_what_changed": case.expectation.require_what_changed,
                "require_zone_mentions": case.expectation.require_zone_mentions,
            },
        }
        if dry_run:
            cases_out.append(entry)
            continue

        reply = generate_deterministic_reply(case)
        diversity_replies = None
        if case.diversity_runs and case.diversity_runs >= 2:
            diversity_replies = [generate_deterministic_reply(case) for _ in range(case.diversity_runs)]

        scored = score_coach_reply(
            reply,
            expectation=case.expectation,
            diversity_replies=diversity_replies,
        )
        entry.update(
            {
                "reply_preview": reply[:400] + ("…" if len(reply) > 400 else ""),
                "reply_words": len(reply.split()),
                "score": scored,
                "diversity_runs": case.diversity_runs or 0,
            }
        )
        cases_out.append(entry)

    if dry_run:
        return {"dry_run": True, "cases": cases_out, "weights": PHASE7_WEIGHTS}

    totals = [item["score"]["total"] for item in cases_out if "score" in item]
    dimension_avgs = {
        key: round(
            sum(item["score"]["dimensions"][key]["score"] for item in cases_out if "score" in item)
            / max(1, len(totals)),
            3,
        )
        for key in PHASE7_WEIGHTS
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "rules",
        "phase": 7,
        "weights": PHASE7_WEIGHTS,
        "summary": {
            "cases": len(cases_out),
            "overall_avg": round(sum(totals) / max(1, len(totals)), 3),
            "dimensions_avg": dimension_avgs,
            "would_read_all": all(
                item.get("score", {}).get("would_read_whole_message") for item in cases_out
            ),
        },
        "cases": cases_out,
    }


def _print_summary(report: dict) -> None:
    if report.get("dry_run"):
        print(f"Dry run — {len(report['cases'])} coach conversation cases:")
        for case in report["cases"]:
            print(f"  • {case['case_id']}: {case['description']}")
        return

    summary = report["summary"]
    print("\nPhase 7 coach conversation eval (rules baseline)")
    print(f"  cases={summary['cases']}  overall_avg={summary['overall_avg']}")
    for key, value in summary["dimensions_avg"].items():
        print(f"  {key}: {value:.3f}")
    print(f"  would_read_all: {summary['would_read_all']}")
    print("\nPer case:")
    for case in report["cases"]:
        total = case["score"]["total"]
        read = "yes" if case["score"]["would_read_whole_message"] else "no"
        print(f"  {case['case_id']}: total={total:.3f}  would_read={read}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 7 coach conversation eval")
    parser.add_argument("--dry-run", action="store_true", help="List cases without scoring")
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Write JSON report (default: results/coach-eval-<timestamp>.json)",
    )
    args = parser.parse_args()

    report = run_eval(dry_run=args.dry_run)
    _print_summary(report)

    if args.dry_run:
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = BACKEND_ROOT / out_path
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = RESULTS_DIR / f"coach-eval-{stamp}.json"

    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
