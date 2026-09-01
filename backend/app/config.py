import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
STRAVA_REDIRECT_URI = os.getenv(
    "STRAVA_REDIRECT_URI",
    "http://localhost:5173/oauth/strava/callback",
)
STRAVA_WEBHOOK_VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "")

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_SCOPES = "read,activity:read_all"

STRAVA_EXPORT_DIR = os.getenv("STRAVA_EXPORT_DIR", "")
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
ACTIVITY_POINTS_DIR = os.getenv(
    "ACTIVITY_POINTS_DIR",
    str(_BACKEND_ROOT / "data" / "activity_points"),
)
STRAVA_UPLOAD_DIR = os.getenv(
    "STRAVA_UPLOAD_DIR",
    str(_BACKEND_ROOT / "data" / "strava_uploads"),
)
MAX_STRAVA_UPLOAD_MB = int(os.getenv("MAX_STRAVA_UPLOAD_MB", "2048"))

# COROS MCP (official remote MCP + OAuth 2.1 PKCE)
COROS_MCP_URL = os.getenv("COROS_MCP_URL", "https://mcp.coros.com/mcp")
COROS_REDIRECT_URI = os.getenv(
    "COROS_REDIRECT_URI",
    "http://localhost:5173/oauth/coros/callback",
)
COROS_MCP_SCOPES = os.getenv(
    "COROS_MCP_SCOPES",
    "openid mcp.tools offline_access",
)
COROS_MCP_CLIENT_ID = os.getenv("COROS_MCP_CLIENT_ID", "")
COROS_OAUTH_CLIENT_FILE = os.getenv(
    "COROS_OAUTH_CLIENT_FILE",
    str(_BACKEND_ROOT / "data" / "coros_oauth_client.json"),
)
COROS_FIT_DAILY_LIMIT = int(os.getenv("COROS_FIT_DAILY_LIMIT", "50"))
COROS_ACTIVITY_LOOKBACK_DAYS = int(os.getenv("COROS_ACTIVITY_LOOKBACK_DAYS", "90"))
COROS_HEALTH_LOOKBACK_DAYS = int(os.getenv("COROS_HEALTH_LOOKBACK_DAYS", "90"))
COROS_FIT_RECENT_LIMIT = int(os.getenv("COROS_FIT_RECENT_LIMIT", "10"))

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-use-long-random-string")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "168"))

# Where the SPA lives, used to build verification links.
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5173").rstrip("/")

# Email (soft verification). "console" just logs the link — fine for local dev.
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "console").strip().lower()
EMAIL_FROM = os.getenv("EMAIL_FROM", "Advance Athlete Lab <no-reply@advanceathletelab.local>")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").strip().lower() != "false"
EMAIL_VERIFY_TTL_HOURS = int(os.getenv("EMAIL_VERIFY_TTL_HOURS", "48"))
EMAIL_VERIFY_RESEND_COOLDOWN_S = int(os.getenv("EMAIL_VERIFY_RESEND_COOLDOWN_S", "60"))

# AI coach
AI_PROVIDER = os.getenv("AI_PROVIDER", "claude").strip().lower()
AI_FALLBACK_PROVIDER = os.getenv("AI_FALLBACK_PROVIDER", "gemini").strip().lower()
AI_REQUEST_TIMEOUT_S = float(os.getenv("AI_REQUEST_TIMEOUT_S", "90"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
AI_LOG_PROMPTS = os.getenv("AI_LOG_PROMPTS", "false").strip().lower() == "true"
