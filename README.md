# Advance Athlete Lab

A personalized **AI fitness coach** and **Digital Twin Periodization Engine** for endurance and multi-sport athletes. The app unifies training data from **Strava** and **COROS**, surfaces health and load metrics, and delivers phase-aware coaching, season planning, and day-to-day autoregulation — with or without an AI provider API key.

## What the app does

| Capability | Description |
|------------|-------------|
| **Unified activity history** | Import and sync activities from Strava and COROS; dedupe across providers; rich activity detail (streams, laps, splits, strength exercises, notes). |
| **Health & recovery** | Sleep, HRV, stress, resting HR, daily health, and recovery views powered by COROS metrics and rolling baselines. |
| **Training analytics** | Training load (TSS/effort), volume & ACWR, fitness trends, and a schedule view aligned with planned workouts. |
| **AI Coach** | Daily advice, weekly brief, chat with intent routing, week plans, and **Today's Call** autoregulation — grounded in a science knowledge base and a deterministic safety layer. |
| **Season planning** | Retrograde periodization from A/B/C/D/E races; baseline & feasibility checks; phase editing, audit, and replan when life or readiness changes. |
| **Cycle-aware coaching** | Optional menstrual cycle tracking with phase context in coach recommendations (opt-in). |
| **Athlete profile** | Onboarding wizard, physiology fields (FTP, LTHR, max HR), events, planning notes, and consent-gated AI coaching. |

## Tech Stack

| Layer | Technology | How it runs |
|-------|------------|-------------|
| **Frontend** | React 18 (Vite) + Tailwind CSS + React Router | Dev server on port `5173` |
| **Backend** | Python FastAPI + SQLAlchemy + Alembic-style migrations | Uvicorn on port `8000` |
| **Database** | PostgreSQL 16 | Docker container on host port `5433` |
| **AI** | Provider-agnostic (`cursor`, `claude`, `openai`, `gemini`) with rules fallback | Backend services |
| **Integrations** | Strava OAuth + webhooks; COROS MCP (OAuth 2.1 PKCE) | Backend sync workers |

## Architecture Overview

Only **PostgreSQL** runs in Docker. The React frontend and FastAPI backend run on your host and connect to the database over `localhost:5433`.

```mermaid
flowchart TB
  subgraph host["Host machine"]
    FE["React SPA<br/>localhost:5173"]
    BE["FastAPI API<br/>localhost:8000"]
  end

  subgraph docker["Docker"]
    PG[("PostgreSQL 16<br/>athlete_lab_postgres<br/>localhost:5433")]
  end

  subgraph external["External services"]
    STRAVA["Strava API"]
    COROS["COROS MCP"]
    AI["AI providers<br/>(optional)"]
  end

  FE -->|"REST + JWT<br/>VITE_API_URL"| BE
  BE -->|"SQLAlchemy<br/>DATABASE_URL"| PG
  BE --> STRAVA
  BE --> COROS
  BE --> AI
  BE -->|"Parquet point data"| FS["backend/data/activity_points/"]
  BE -->|"Science corpus"| KB["backend/data/science_corpus/"]
```

### Request flow

1. The SPA calls REST endpoints under `/api/*` with a JWT from `/api/auth/login` or `/api/auth/register`.
2. FastAPI routes validate input with Pydantic schemas, load the athlete profile, and delegate to service modules.
3. SQLAlchemy persists relational data; high-frequency activity streams are stored as Parquet files on disk.
4. The AI coach layer always runs a **deterministic safety pass** before returning plans, advice, or chat — even when an LLM generates the draft.

## App navigation

| Section | Routes | Purpose |
|---------|--------|---------|
| **Home** | `/dashboard` | Overview, connections, Today's Call, quick links |
| **Coach** | `/coach` | AI chat, daily advice, week plan, week brief |
| **Health & Recovery** | `/health/recovery`, `/sleep`, `/hrv`, `/stress`, `/rhr`, `/daily` | COROS-backed health metrics with guides |
| **Training** | `/training/load`, `/volume`, `/fitness`, `/schedule`, `/season` | Load, ACWR, fitness, schedule, season timeline |
| **Activities** | `/activities`, `/activities/:id` | Filterable history and sport-specific detail pages |
| **Account** | `/profile`, `/settings` | Profile, events, cycle tracking, integrations, consent |

Onboarding flow: **Sign in → Onboarding → Connect Strava (optional step) → Connect COROS (optional step) → Dashboard**.

## Backend services (high level)

```
backend/app/
├── routes/          # REST API (auth, activities, strava, coros, coach, season, cycle, biometrics, science)
├── services/
│   ├── ai_coach.py, coach_ai.py, coach_intent.py, coach_safety.py, coach_templates.py
│   ├── periodization.py, season_baseline.py, season_replan.py, season_audit.py
│   ├── autoregulation.py, training_load.py, athlete_coach_context.py
│   ├── menstrual_engine.py, zone_recalibration.py, b_race_calibration.py
│   ├── strava_sync.py, coros_sync.py, activity_dedupe.py, activity_detail.py
│   ├── biometric_sync.py, biometric_baselines.py, science_kb.py
│   └── planning_notes.py
├── models.py        # Users, profiles, activities, season plans, events, advice snapshots, biometrics
└── migrate.py       # Incremental schema migrations on startup
```

## Project structure

```
Advance athlete lab/
├── backend/
│   ├── app/                 # FastAPI application
│   ├── data/
│   │   ├── activity_points/ # Parquet stream storage
│   │   └── science_corpus/  # Curated coaching evidence chunks
│   ├── scripts/
│   │   ├── ai_eval/         # Coach quality evaluation harness
│   │   └── science_ingest/  # Corpus indexing
│   ├── tests/               # Pytest suite
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/             # API clients (auth, coach, season, coros, strava, activities)
│       ├── components/      # UI (coach, season, activity, health, layout, profile)
│       ├── pages/           # Route-level pages
│       └── utils/           # Formatters, guides, onboarding steps
├── docs/
│   ├── ai-provider-evaluation.md
│   └── science-kb-policy.md
├── docker-compose.yml       # PostgreSQL only
├── .env.example             # Environment template
└── README.md
```

## Prerequisites

- Docker and Docker Compose
- Python **3.11+** (use 3.11 for `fit2gpx`; 3.13 may fail)
- Node.js **18+**

## Quick Start

### 1. Environment files

```bash
cp .env.example backend/.env
echo "VITE_API_URL=http://localhost:8000" > frontend/.env
```

Edit `backend/.env` with your Strava/COROS/AI keys as needed (see [Environment Variables](#environment-variables)).

### 2. Start PostgreSQL

```bash
docker compose up -d
docker compose ps   # wait until postgres is healthy
```

### 3. Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

---

## Integrations

### Strava

1. Create a Strava API application at https://www.strava.com/settings/api
2. Set **Authorization Callback Domain** to `localhost`
3. Add to `backend/.env`:

```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REDIRECT_URI=http://localhost:5173/oauth/strava/callback
STRAVA_WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token
```

4. Connect from the dashboard or onboarding flow.
5. For webhooks in local dev, expose the backend with ngrok and register `https://<id>.ngrok.io/strava/webhook`.

**Bulk export import:** Upload a Strava export zip from the dashboard, or set `STRAVA_EXPORT_DIR` and use the CLI import script.

### COROS

COROS uses the official remote MCP with OAuth 2.1 PKCE:

```env
COROS_MCP_URL=https://mcp.coros.com/mcp
COROS_REDIRECT_URI=http://localhost:5173/oauth/coros/callback
COROS_FIT_DAILY_LIMIT=50
COROS_ACTIVITY_LOOKBACK_DAYS=90
COROS_HEALTH_LOOKBACK_DAYS=28
```

Connect from onboarding or Settings, then sync activities and health metrics. FIT files enrich activity detail and strength parsing.

---

## AI Coach

The coach combines four layers and works **without** an API key (rules/templates mode):

1. **Athlete context** — profile, physiology, recent activities, COROS health/load, season phase, cycle context (if enabled), readiness flags.
2. **Science knowledge base** — curated, citable chunks under `backend/data/science_corpus/`. Policy: [`docs/science-kb-policy.md`](docs/science-kb-policy.md).
3. **Deterministic safety layer** — `coach_safety.py` enforces caps (weekly minutes, hard sessions, injury contraindications, spine lock, ACWR veto) and repairs or blocks unsafe output.
4. **LLM generation (optional)** — plans, advice, chat, and season-aware prompts when a provider key is configured.

```env
AI_PROVIDER=cursor          # cursor | claude | openai | gemini
AI_FALLBACK_PROVIDER=
CURSOR_API_KEY=...          # or ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY
AI_REQUEST_TIMEOUT_S=90
AI_LOG_PROMPTS=false
```

Provider evaluation methodology: [`docs/ai-provider-evaluation.md`](docs/ai-provider-evaluation.md).

```bash
cd backend
python scripts/ai_eval/run_eval.py --provider rules
python scripts/ai_eval/run_eval.py --provider claude --provider gemini
python scripts/ai_eval/smoke_coach.py
```

AI coaching requires explicit consent on the athlete profile; coach endpoints return `403` until granted.

### Coach API highlights

| Endpoint | Description |
|----------|-------------|
| `GET /api/coach/status` | Provider chain, consent, KB state |
| `GET /api/coach/context` | Unified athlete context for the UI |
| `GET /api/coach/todays-call` | Autoregulation tier and session guidance |
| `GET/POST /api/coach/plan` | Weekly training plan |
| `GET /api/coach/advice` | Today's readiness guidance |
| `GET /api/coach/week-brief` | Weekly advice brief (with optional refresh/topic) |
| `GET/POST /api/coach/chat` | Coach chat with intent routing |
| `POST /api/coach/plan/from-chat` | Apply a chat-revised week plan |
| `POST /api/coach/baseline/confirm` | Confirm athlete baseline for planning |
| `GET /api/coach/planned-workouts` | Schedule-compatible planned rows |

---

## Digital Twin Periodization & Season Planning

The **Season** page (`/training/season`) is the control centre for long-range training structure:

- **Retrograde periodization** — phases (Base → Build → Peak → Taper → Restore) computed backward from your A-race and supporting B/C/D/E events.
- **Athlete baseline** — recent training volume, long-session ceiling, and feasibility projection for the A-race target.
- **Race feasibility** — flags when current load trajectory may not support the stated goal date or target.
- **Season audit** — structured review of phase balance, recovery gaps, and event spacing before committing a plan.
- **Replan engine** — detects triggers (missed load, injury flag, event date change) and proposes phase adjustments.
- **Phase editing** — shift, replace, patch, or delete individual phases without rebuilding from scratch.
- **Planning notes** — free-text context on the profile/onboarding that flows into season generation and coach prompts.
- **B-race calibration & D-race zone tests** — post-race result capture and automatic zone recalibration flows.

### Season API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/season` | Active season plan with phases, baseline, feasibility |
| GET | `/api/season/preview` | Preview plan before generation |
| POST | `/api/season/generate` | Generate a new season plan |
| GET | `/api/season/audit` | Run season audit on current/proposed plan |
| GET | `/api/season/replan/triggers` | List active replan triggers |
| POST | `/api/season/replan` | Execute a season replan |
| PATCH | `/api/season/phases/{id}` | Adjust phase parameters |
| POST | `/api/season/phases/{id}/shift` | Shift a phase on the timeline |
| POST | `/api/season/phases/{id}/replace` | Replace a phase |
| DELETE | `/api/season/phases/{id}` | Remove a phase |
| GET/POST/PATCH/DELETE | `/api/season/events` | CRUD for athlete events (A/B/C/D/E races) |
| POST | `/api/season/events/{id}/complete` | Log race result and trigger calibration |

Season context is injected into coach weekly prompts, Today's Call, and safety checks so daily guidance stays aligned with the macro plan.

---

## Health, load & cycle tracking

| Feature | Backend | Frontend |
|---------|---------|----------|
| COROS health sync | `coros_sync.py`, `biometric_sync.py` | Health pages under `/health/*` |
| Rolling baselines | `biometric_baselines.py` | Zone strips, gauges, metric guides |
| Unified ACWR / TSS | `training_load.py` | Training Load & Volume pages |
| Manual biometrics | `POST /api/biometrics/manual` | Profile / health inputs |
| Cycle tracking (opt-in) | `menstrual_engine.py`, `/api/cycle/*` | Profile panel + coach phase chip |

---

## API Endpoints (summary)

### Auth & profile

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register user + athlete profile |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Current user |
| POST | `/api/auth/verify-email/request` | Send verification email |
| POST | `/api/auth/verify-email/confirm` | Confirm email token |
| GET/PATCH | `/api/profile/me` | Read/update profile |
| POST | `/api/profile/onboarding` | Complete onboarding wizard |

### Activities

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/activities` | Paginated activity list (filters, providers) |
| GET | `/api/activities/summary` | Monthly volume summary |
| GET | `/api/activities/{id}` | Activity detail |
| POST | `/api/activities/{id}/enrich` | Fetch/sync detailed streams |
| GET/PATCH/POST/DELETE | `/api/activities/{id}/notes` | Activity notes CRUD |
| POST | `/api/activities/dedupe` | Cross-provider deduplication |

### Strava & COROS

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/strava/auth` | OAuth URL |
| POST | `/api/strava/callback` | Exchange OAuth code |
| POST | `/api/strava/sync` | Start background sync |
| GET | `/api/coros/auth` | COROS OAuth URL |
| POST | `/api/coros/callback` | COROS token exchange |
| POST | `/api/coros/sync` | Sync activities + health |
| GET | `/api/coros/overview` | COROS dashboard payload |

### Science knowledge base

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/science/sources` | List corpus sources |
| GET | `/api/science/search` | Search citable evidence chunks |

Full interactive docs: http://localhost:8000/docs

---

## Environment Variables

| Variable | Used by | Default | Description |
|----------|---------|---------|-------------|
| `DATABASE_URL` | Backend | `postgresql+psycopg2://athlete:athlete@localhost:5433/athlete_lab` | SQLAlchemy connection (host port **5433**) |
| `VITE_API_URL` | Frontend | `http://localhost:8000` | API base URL |
| `JWT_SECRET` | Backend | `change-me-in-production-...` | JWT signing secret |
| `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` | Backend | — | Strava OAuth credentials |
| `STRAVA_REDIRECT_URI` | Backend | `http://localhost:5173/oauth/strava/callback` | OAuth redirect |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Backend | — | Webhook validation secret |
| `STRAVA_EXPORT_DIR` | Backend | — | Path to unzipped Strava bulk export |
| `ACTIVITY_POINTS_DIR` | Backend | `./data/activity_points` | Parquet point-data directory |
| `COROS_MCP_URL` | Backend | `https://mcp.coros.com/mcp` | COROS MCP endpoint |
| `COROS_REDIRECT_URI` | Backend | `http://localhost:5173/oauth/coros/callback` | COROS OAuth redirect |
| `COROS_FIT_DAILY_LIMIT` | Backend | `50` | Max FIT downloads per day |
| `APP_BASE_URL` | Backend | `http://localhost:5173` | SPA URL for email links |
| `EMAIL_PROVIDER` | Backend | `console` | `console` \| `resend` \| `smtp` |
| `AI_PROVIDER` | Backend | `claude` | Primary coach provider |
| `AI_FALLBACK_PROVIDER` | Backend | `gemini` | Fallback provider |
| `CURSOR_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | Backend | — | Provider credentials |
| `AI_LOG_PROMPTS` | Backend | `false` | Log redacted prompts for debugging |
| `AI_DEBUG` | Backend | `false` | Show provider chain in `/coach/status` |

See `.env.example` for the full list including SMTP and model overrides.

---

## Testing

```bash
cd backend
source .venv/bin/activate
pytest                           # full suite
pytest tests/test_periodization.py tests/test_season_baseline.py tests/test_season_replan.py
pytest tests/test_ai_coach.py tests/test_autoregulation.py
pytest tests/test_menstrual_engine.py tests/test_spine_lock.py
```

Key test areas: periodization, season baseline/feasibility/audit/replan, coach intent & safety, clinical veto, science grounding, and week-plan flow.

---

## Docker commands

Run from the **project root**:

```bash
docker compose up -d              # start PostgreSQL
docker compose ps                 # check health
docker compose logs -f postgres   # follow logs
docker compose exec postgres psql -U athlete -d athlete_lab
docker compose down               # stop containers (volume preserved)
docker compose down -v            # stop and delete data (destructive)
```

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Backend cannot connect to DB | `docker compose ps` — Postgres should be `healthy`. Use port **5433** in `DATABASE_URL`. |
| Frontend network/CORS errors | Backend on `8000`; `VITE_API_URL` matches. Restart Vite after `.env` changes. |
| Port 5433 in use | Change host port in `docker-compose.yml` and update `DATABASE_URL`. |
| Strava connect fails | Credentials in `backend/.env` match Strava app settings and redirect URI. |
| COROS sync empty | Complete OAuth; check MCP URL and lookback day settings. |
| Coach returns 403 | Enable AI coaching consent on the athlete profile. |
| Import / FIT errors | Use Python 3.11 venv; ensure `fit2gpx` and `lxml` installed. |
| AI coach uses rules only | No provider key set — expected. Add `CURSOR_API_KEY` or other provider key. |
| Season plan won't generate | Set an A-race event and confirm baseline; check `/api/season/preview` warnings. |

---

## Verification (smoke test)

```bash
# Health check
curl http://localhost:8000/

# Register (returns JWT)
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","name":"Alex","age":30,"weight":70,"fitness_goals":"Half marathon"}'

# Coach status (requires auth header from register response)
curl http://localhost:8000/api/coach/status \
  -H "Authorization: Bearer YOUR_JWT"
```

---

## License & docs

- Science KB policy: [`docs/science-kb-policy.md`](docs/science-kb-policy.md)
- AI provider evaluation: [`docs/ai-provider-evaluation.md`](docs/ai-provider-evaluation.md)
