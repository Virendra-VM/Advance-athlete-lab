"""Phase E — coach quality regression harness.

Routing bank (200+ cases) + mechanical reply scoring for deploy gates.

    python scripts/ai_eval/run_coach_quality_eval.py --dry-run
    python scripts/ai_eval/run_coach_quality_eval.py
    python scripts/ai_eval/run_coach_quality_eval.py --output results/phase-e.json
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

from app.services.coach_quality_eval import (  # noqa: E402
    run_grounding_regression,
    run_quality_regression,
    run_routing_regression,
)
from scripts.ai_eval.coach_conversation_cases import COACH_CONVERSATION_CASES  # noqa: E402
from scripts.ai_eval.coach_golden_bank import (  # noqa: E402
    GOLDEN_ROUTING_CASES,
    GROUNDING_EVAL_CASES,
)
from scripts.ai_eval.coach_reply_generator import generate_deterministic_reply  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def run_phase_e_eval(*, dry_run: bool = False) -> dict:
    if dry_run:
        return {
            "dry_run": True,
            "phase": "E",
            "routing_cases": len(GOLDEN_ROUTING_CASES),
            "grounding_cases": len(GROUNDING_EVAL_CASES),
            "quality_cases": len(COACH_CONVERSATION_CASES),
            "golden_categories": sorted({case.category for case in GOLDEN_ROUTING_CASES}),
        }

    routing = run_routing_regression(GOLDEN_ROUTING_CASES)
    grounding = run_grounding_regression(GROUNDING_EVAL_CASES)
    reply_cases: list[tuple] = []
    for case in COACH_CONVERSATION_CASES:
        reply = generate_deterministic_reply(case)
        reply_cases.append((case, reply, case.expectation))
    quality = run_quality_regression(reply_cases)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "E",
        "routing": routing,
        "grounding": grounding,
        "quality": quality,
        "summary": {
            "routing_pass_rate": routing["pass_rate"],
            "routing_regression_pass": routing["regression_pass"],
            "grounding_pass_rate": grounding["pass_rate"],
            "grounding_regression_pass": grounding["regression_pass"],
            "quality_avg": quality["overall_avg"],
            "quality_regression_pass": quality["regression_pass"],
            "deploy_gate_pass": (
                routing["regression_pass"]
                and grounding["regression_pass"]
                and quality["regression_pass"]
            ),
        },
    }


def _print_summary(report: dict) -> None:
    if report.get("dry_run"):
        print(f"Dry run — Phase E: {report['routing_cases']} routing cases")
        print(f"  grounding cases: {report['grounding_cases']}")
        print(f"  quality subset: {report['quality_cases']} Phase 7 cases + golden picks")
        print(f"  categories: {', '.join(report['golden_categories'])}")
        return

    summary = report["summary"]
    print("\nPhase E coach quality regression")
    print(f"  routing: {summary['routing_pass_rate']:.1%} pass ({report['routing']['passed']}/{report['routing']['total']})")
    print(
        f"  grounding: {summary['grounding_pass_rate']:.1%} pass "
        f"({report['grounding']['passed']}/{report['grounding']['total']})"
    )
    print(f"  quality avg: {summary['quality_avg']:.3f}")
    print(f"  deploy gate: {'PASS' if summary['deploy_gate_pass'] else 'FAIL'}")
    if report["routing"]["failures"]:
        print("\nRouting failures (first 10):")
        for row in report["routing"]["failures"][:10]:
            print(
                f"  {row['case_id']}: skill={row['actual_skill']} "
                f"(expected one of {row['acceptable_skills']})"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase E coach quality regression")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    report = run_phase_e_eval(dry_run=args.dry_run)
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
        out_path = RESULTS_DIR / f"coach-quality-e-{stamp}.json"

    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nReport written to {out_path}")

    if not report["summary"]["deploy_gate_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
