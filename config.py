import os
import base64

from dotenv import load_dotenv


# Load variables from a .env file into the environment
load_dotenv()


def _is_base64(value: str) -> bool:
    try:
        # validate=True ensures only proper base64 passes
        base64.b64decode(value, validate=True)
        return True
    except Exception:
        return False


def _normalize_gigachat_credentials(raw_value: str) -> str:
    """Return ONLY base64(client_id:client_secret), without the "Basic " prefix.

    Accepts the following input forms from env:
    - "client_id:client_secret" (auto-encodes)
    - "Basic <base64>" (strips prefix and returns <base64>)
    - "<base64>" (passes through)
    - "Basic client:secret" (encodes and returns base64)
    """
    value = (raw_value or "").strip()

    if value.lower().startswith("basic "):
        payload = value[6:].strip()
        if _is_base64(payload):
            return payload
        if ":" in payload:
            return base64.b64encode(payload.encode("utf-8")).decode("ascii")
        # Unknown format after Basic -> return as-is (might already be token-like)
        return payload

    if _is_base64(value):
        return value
    if ":" in value:
        return base64.b64encode(value.encode("utf-8")).decode("ascii")
    # Last resort: assume already a base64 or token-like string
    return value


# Public constants used across the app
TOKEN = os.getenv("TOKEN")
AUTH_GIGA_RAW = os.getenv("AUTH_GIGA")
PROXY_URL = os.getenv("PROXY_URL")  # Optional: e.g., socks5://user:pass@host:port or http://host:port


if not TOKEN:
    raise RuntimeError("Environment variable TOKEN is not set. Add it to your .env file.")

if not AUTH_GIGA_RAW:
    raise RuntimeError("Environment variable AUTH_GIGA is not set. Add it to your .env file.")

# Normalize to the exact format expected by GigaChat OAuth
AUTH_GIGA = _normalize_gigachat_credentials(AUTH_GIGA_RAW)