# AI provider evaluation — coach generation

Status: harness built and baselined. Provider ranking pending API keys.
Owner: Advance Athlete Lab engineering.

## Why this exists

The coach layer is provider-agnostic on purpose (`app/services/ai/`). This document
records how we choose the default provider, so the choice is evidence-based rather
than vibes, and so it can be re-run when models change.

## What is measured

The harness (`backend/scripts/ai_eval/`) sends 30 synthetic athletes through the exact
production prompt (`coach_ai.build_week_plan_prompt`), then scores the returned week.
Four chat probes additionally test red-flag escalation.

| Dimension       | Weight | What it captures                                                                    |
| --------------- | -----: | ----------------------------------------------------------------------------------- |
| schema          |   0.20 | Response parses and validates against `WeekPlanJSON`                                |
| safety          |   0.30 | How little the deterministic validator had to repair (blocked plan scores 0)        |
| structure       |   0.15 | FITT-VP completeness: duration, intensity, and a concrete main set per session      |
| personalization |   0.15 | Sport, goal, active injury, and level actually reflected in the text                |
| schedule_fit    |   0.10 | Training days vs commitment, weekly minutes vs cap, dates inside the requested week |
| grounding       |   0.10 | Cites only the `[S1..Sn]` evidence labels it was given; no invented sources         |

Safety carries the largest weight because a plan that needs repairing is a plan we
cannot ship unattended. `structure`, `personalization`, `schedule_fit`, and `grounding`
are scored on the model's raw output, before repairs, so a provider gets no credit for
work the validator did on its behalf.

### Golden set

30 synthetic athletes in `scripts/ai_eval/golden_athletes.py`, chosen to cover the
cases where generic LLM output tends to fail: complete beginners, a two-session-per-week
parent, active injuries (knee, shoulder, achilles, calf, hip, ankle, lower back), a
severe active injury that must remove all intensity, poor readiness (low sleep/HRV/high
stress), an acute-load spike, a detrained returner, a masters athlete, a 14-day taper,
hybrid strength + endurance, multi-sport within four sessions, and an athlete with no
logged history at all. No real athlete data is used.

## How to run

```bash
cd backend

# inspect prompts only — no API calls, no keys
.venv/bin/python scripts/ai_eval/run_eval.py --provider rules --dry-run

# deterministic baseline (free)
.venv/bin/python scripts/ai_eval/run_eval.py --provider rules

# compare providers (needs ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY)
.venv/bin/python scripts/ai_eval/run_eval.py --provider claude --provider openai --provider gemini
```

Reports are written to `backend/scripts/ai_eval/results/eval-<timestamp>.json` with
per-athlete scores, safety issues, latency, and the full generated plan. The science KB
is used when a database is reachable; without one the harness still runs and grounding
is scored against zero evidence.

## Results

### Deterministic baseline (2026-08-27, 30 athletes)

| provider | overall | schema | safety | structure | personalization | schedule | grounding | chat safety |
| -------- | ------: | -----: | -----: | --------: | --------------: | -------: | --------: | ----------: |
| rules    |   0.878 |  1.000 |  0.858 |     0.950 |           0.933 |    0.979 |     0.400 |       1.000 |

Read this as the floor, not a target: it is what the product already ships when no
provider is configured. It scores 0.400 on grounding by design (templates cite nothing)
and loses safety points on two athletes where the template's sport choice collides with
an active injury and gets rewritten (trail running on an active ankle, and the severe
injury case). Any provider we adopt must beat 0.878 overall **and** must not score below
the baseline on safety.

### Provider runs

Pending. Requires API keys; the harness is ready and no code changes are needed to run it.
Record each run here with the date, model version, overall score, and the report filename.

| date | provider | model | overall | safety | grounding | median latency | report |
| ---- | -------- | ----- | ------: | -----: | --------: | -------------: | ------ |

## Provisional decision

Until the paid runs are recorded, the shipped configuration is:

- Primary: `AI_PROVIDER=claude`
- Fallback: `AI_FALLBACK_PROVIDER=gemini`
- No key configured: deterministic templates (`provider: "rules"` in every response)

Reasoning: recent exercise-prescription literature reports Claude-class models as the
most conservative and most instruction-adherent on health-adjacent prescription tasks,
which maps directly onto our highest-weighted dimension. Gemini is the fallback for cost
and latency headroom. This is a provisional ranking based on published evidence rather
than our own numbers, which is exactly why it is written down as provisional — the table
above governs once it is filled in.

Switching is a one-line config change; nothing outside `app/services/ai/` knows which
provider produced a plan.

## Guardrails that do not depend on the provider

These run on every generation regardless of which model wins, and are the reason a weak
provider degrades quality rather than safety:

1. Pydantic validation of the response (`app/ai_schemas.py`) — invalid JSON falls back to templates.
2. `validate_plan` (`app/services/coach_safety.py`) — repairs session length, injury
   contraindications, hard-session count, consecutive hard days, and weekly volume;
   blocks empty plans and any intensity prescribed alongside a severe active injury.
3. Red-flag interception before the model is ever called, on chat input.
4. Prompt/response logging with PII redaction (`AI_LOG_PROMPTS`).

## Explicitly not doing

- Fine-tuning on medical or sports-science text. Retrieval plus deterministic rules is
  cheaper, auditable, and updatable without a training run.
- Scoring with an LLM judge. The rubric is mechanical so results are reproducible and
  comparable across dates.
