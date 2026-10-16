"""Runtime settings, read from environment variables.

Nothing secret is hard-coded. Copy .env.example to .env for local runs, and set
the same variables in the Alternate Clouds service settings for deployment.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"


def _load_dotenv() -> None:
    """Minimal .env loader so local runs work without extra packages."""
    env_file = BASE_DIR.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# AI model provider: "gemini", "openai" (any OpenAI-compatible API such as Groq), or "none".
LLM_PROVIDER = env("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.8-flash")
# Optional second model to try when the first is overloaded (leave empty to disable)
GEMINI_FALLBACK_MODEL = env("GEMINI_FALLBACK_MODEL")
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_BASE_URL = env("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
OPENAI_MODEL = env("OPENAI_MODEL", "llama-3.3-70b-versatile")
OPENAI_VISION_MODEL = env("OPENAI_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
LLM_TIMEOUT = float(env("LLM_TIMEOUT", "20"))

# Optional email sending (for the doctor review link). Leave empty to show the link on screen instead.
SMTP_HOST = env("SMTP_HOST")
SMTP_PORT = int(env("SMTP_PORT", "587") or 587)
SMTP_USER = env("SMTP_USER")
SMTP_PASSWORD = env("SMTP_PASSWORD")
SMTP_FROM = env("SMTP_FROM") or SMTP_USER

# Public URL of the deployment, used in doctor review links. If empty, taken from the request.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL").rstrip("/")

# SQLite database location. /data is a good choice inside the container.
DB_PATH = env("DB_PATH", str(BASE_DIR.parent / "medpassport.db"))

# External drug database (US National Library of Medicine, free, no key).
RXNORM_BASE_URL = env("RXNORM_BASE_URL", "https://rxnav.nlm.nih.gov/REST")
RXNORM_ENABLED = env("RXNORM_ENABLED", "true").lower() == "true"
HTTP_TIMEOUT = float(env("HTTP_TIMEOUT", "5"))

# Seed a demo case on first start so judges always see a complete example.
SEED_DEMO = env("SEED_DEMO", "true").lower() == "true"

MAX_MEDICINES = 15
MAX_COUNTRIES = 8
MAX_IMAGE_BYTES = 6 * 1024 * 1024