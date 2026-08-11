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
