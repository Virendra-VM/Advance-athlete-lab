# Advance Athlete Lab

Phase 1 foundation for a personalized AI fitness coach application.

## Tech Stack

| Layer | Technology | How it runs |
|-------|------------|-------------|
| **Frontend** | React (Vite) + Tailwind CSS | Local dev server on port `5173` |
| **Backend** | Python FastAPI + SQLAlchemy | Local Uvicorn server on port `8000` |
| **Database** | PostgreSQL 16 | Docker container on port `5432` |

## Architecture Overview

In Phase 1, only **PostgreSQL** is Dockerized. The React frontend and FastAPI backend run on your host machine and connect to the database container over `localhost`.

```mermaid
flowchart LR
  subgraph host["Host machine"]
    FE["React frontend<br/>localhost:5173"]
    BE["FastAPI backend<br/>localhost:8000"]
  end

  subgraph docker["Docker"]
    PG[("PostgreSQL<br/>athlete_lab_postgres<br/>localhost:5432")]
  end

  FE -->|"HTTP fetch (JSON)<br/>VITE_API_URL"| BE
  BE -->|"SQLAlchemy + psycopg2<br/>DATABASE_URL"| PG
```

### How the React frontend talks to FastAPI

1. **API client** — `frontend/src/api/athlete.js` uses the browser `fetch` API to call REST endpoints under `/api/athletes`.
2. **Base URL** — Requests go to `VITE_API_URL` (default `http://localhost:8000`), set in `.env.example` and copied to `frontend/.env` if needed.
3. **CORS** — FastAPI enables cross-origin requests from any `localhost` or `127.0.0.1` port via `CORSMiddleware` in `backend/app/main.py`, so the Vite dev server (`5173`) can call the API (`8000`) without a proxy.
4. **Data flow** — Components such as `Dashboard.jsx` call helpers like `listAthleteProfiles()` and `createAthleteProfile()`. The backend validates JSON with Pydantic schemas, persists rows via SQLAlchemy, and returns JSON responses.

Example request path when loading the dashboard:

```
Dashboard.jsx → athlete.js → GET http://localhost:8000/api/athletes → FastAPI router → PostgreSQL
```

### How PostgreSQL is connected

1. **Docker Compose** — `docker-compose.yml` starts a `postgres:16-alpine` container named `athlete_lab_postgres` with:
   - User / password: `athlete` / `athlete`
   - Database: `athlete_lab`
   - Port mapping: `5432:5432` (container port exposed on the host)
   - Named volume `postgres_data` for persistent storage
   - Health check via `pg_isready` so you can confirm the DB is ready before starting the backend

2. **Backend connection string** — `backend/app/database.py` reads `DATABASE_URL` from the environment (see `.env.example`):

   ```
   postgresql+psycopg2://athlete:athlete@localhost:5432/athlete_lab
   ```

   Because the backend runs on the host (not inside Docker), it reaches PostgreSQL through `localhost:5432`.

3. **ORM & schema** — SQLAlchemy creates the `athlete_profiles` table on startup (`Base.metadata.create_all` in the FastAPI lifespan handler). Route handlers in `backend/app/routes/athletes.py` use a per-request DB session from `get_db()`.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (use 3.11 for `fit2gpx` — Python 3.13 is not supported yet)
- Node.js 18+

## Project Structure

```
Advance athlete lab/
├── backend/              # FastAPI + SQLAlchemy
│   └── app/
│       ├── main.py       # App entry, CORS, table creation
│       ├── database.py   # Engine, session, DATABASE_URL
│       ├── models.py     # AthleteProfile SQLAlchemy model
│       ├── schemas.py    # Pydantic request/response models
│       └── routes/       # /api/athletes endpoints
├── frontend/             # React + Vite + Tailwind
│   └── src/
│       ├── api/athlete.js
│       └── components/
├── docker-compose.yml    # PostgreSQL service
└── .env.example          # Shared env template
```

## Quick Start

### 1. Environment files

```bash
cp .env.example backend/.env
# Optional: copy VITE_API_URL for the frontend
echo "VITE_API_URL=http://localhost:8000" > frontend/.env
```

### 2. Start PostgreSQL (Docker)

From the project root:

```bash
docker compose up -d
```

Wait until the container is healthy:

```bash
docker compose ps
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

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

---

## Docker Commands

All commands below are run from the **project root** (where `docker-compose.yml` lives).

### Start containers

```bash
# Start PostgreSQL in the background
docker compose up -d

# Start and rebuild (if you change compose config)
docker compose up -d --build
```

### Stop containers

```bash
# Stop containers but keep the postgres_data volume
docker compose stop

# Stop and remove containers (data volume is preserved)
docker compose down

# Stop, remove containers, AND delete the database volume (destructive)
docker compose down -v
```

### View logs

```bash
# Follow logs for all services
docker compose logs -f

# Follow logs for PostgreSQL only
docker compose logs -f postgres

# Show last 100 lines without following
docker compose logs --tail=100 postgres
```

### Other useful commands

```bash
# Container status and health
docker compose ps

# Open a psql shell inside the running container
docker compose exec postgres psql -U athlete -d athlete_lab

# Restart PostgreSQL
docker compose restart postgres
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/athletes` | Create athlete profile |
| GET | `/api/athletes` | List all profiles |
| GET | `/api/athletes/{id}` | Get profile by ID |
| GET | `/api/strava/auth` | Get Strava OAuth authorization URL |
| POST | `/api/strava/callback` | Exchange OAuth code for tokens |
| GET | `/api/strava/status` | Check Strava connection status |
| GET | `/strava/webhook` | Strava webhook subscription validation |
| POST | `/strava/webhook` | Receive Strava activity webhook events |
| POST | `/api/import/strava-history/upload` | Upload Strava bulk export zip and start import |
| POST | `/api/import/strava-history` | Start import from `STRAVA_EXPORT_DIR` (dev/CLI) |
| GET | `/api/import/strava-history/status` | Bulk import job progress |
| GET | `/api/activities` | List imported activities for an athlete |
| GET | `/api/activities/summary` | Monthly distance summary for charts |
| GET | `/api/activities/{id}` | Get a single imported activity |

### Athlete profile fields

- `name` — athlete name
- `age` — age in years
- `weight` — weight in kg
- `fitness_goals` — training goals
- `medical_history` — relevant medical notes (nullable)

## Verification

```bash
# Create a profile
curl -X POST http://localhost:8000/api/athletes \
  -H "Content-Type: application/json" \
  -d '{"name":"Alex","age":28,"weight":75.5,"fitness_goals":"Build strength","medical_history":"None"}'

# List profiles
curl http://localhost:8000/api/athletes

# Fetch profile by ID
curl http://localhost:8000/api/athletes/1

# Validate Strava webhook subscription
curl "http://localhost:8000/strava/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=YOUR_TOKEN"
```

## Strava Setup (Phase 2)

1. Create a Strava API application at https://www.strava.com/settings/api
2. Set **Authorization Callback Domain** to `localhost`
3. Copy your credentials into **`backend/.env`** (not the frontend):

```env
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_REDIRECT_URI=http://localhost:5173/oauth/strava/callback
STRAVA_WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token_here
```

4. In the app dashboard, click **Connect to Strava** to complete OAuth
5. For webhook testing in local dev, expose the backend with ngrok (e.g. `https://abc123.ngrok.io/strava/webhook`) and create a Strava webhook subscription pointing to that URL

## Strava Bulk Export Import (Phase 2 Part 2)

1. Request a bulk export from Strava and download the zip file (do not unzip)
2. In the app dashboard, click **Upload Strava Export** and select the zip file
3. Wait for upload + import progress to finish — activity history appears below your profile

Optional CLI / server-path import (for developers):

```env
STRAVA_EXPORT_DIR=/Users/you/Downloads/strava_export
```

```bash
cd backend
python scripts/import_strava_history.py --athlete-profile-id 1
```

Summary metrics are stored in PostgreSQL (`activities` table); second-by-second point data is saved as Parquet files under `backend/data/activity_points/`.

**Note:** `fit2gpx` may require Python 3.11 or 3.12 if installation fails on Python 3.13.

## Environment Variables

| Variable | Used by | Default | Description |
|----------|---------|---------|-------------|
| `DATABASE_URL` | Backend | `postgresql+psycopg2://athlete:athlete@localhost:5432/athlete_lab` | SQLAlchemy connection string |
| `VITE_API_URL` | Frontend | `http://localhost:8000` | FastAPI base URL for browser requests |
| `STRAVA_CLIENT_ID` | Backend | — | Strava app client ID |
| `STRAVA_CLIENT_SECRET` | Backend | — | Strava app client secret (backend only) |
| `STRAVA_REDIRECT_URI` | Backend | `http://localhost:5173/oauth/strava/callback` | OAuth redirect URI registered with Strava |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Backend | — | Secret token for Strava webhook validation |
| `STRAVA_EXPORT_DIR` | Backend | — | Absolute path to unzipped Strava bulk export folder |
| `ACTIVITY_POINTS_DIR` | Backend | `./data/activity_points` | Directory for Parquet point-data files |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Backend cannot connect to DB | Run `docker compose ps` — Postgres should be `healthy`. Confirm `DATABASE_URL` uses `localhost:5432`. |
| Frontend shows network/CORS errors | Ensure the backend is running on port `8000` and `VITE_API_URL` matches. Restart Vite after changing `.env`. |
| Port 5432 already in use | Stop a local PostgreSQL instance or change the host port in `docker-compose.yml` (e.g. `"5433:5432"`) and update `DATABASE_URL` accordingly. |
| Empty dashboard after login | Use **Create Sample Profile** in the UI, or POST a profile via `curl` (see Verification). |
| Strava connect fails | Confirm `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, and `STRAVA_REDIRECT_URI` are set in `backend/.env` and match your Strava app settings. |
| Import shows 0 imported / 1 error | Restart backend using Python 3.11 venv: `python3.11 -m venv .venv && pip install -r requirements.txt`. Needs `fit2gpx` + `lxml`. |
