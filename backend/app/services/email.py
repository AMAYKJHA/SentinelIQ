import logging
import re
from functools import lru_cache
from pathlib import Path

import httpx

from app.core.config import APP_DIR, settings
from app.schemas.dto import EmailSchema

logger = logging.getLogger(__name__)

TEMPLATE_DIR = APP_DIR / "templates" / "email"
_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@lru_cache(maxsize=32)
def _load_template(name: str) -> str:
    path: Path = TEMPLATE_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Email template not found: {name}")
    return path.read_text(encoding="utf-8")


def _render(template_name: str, params: dict) -> str:
    raw = _load_template(template_name)

    def replace(match: re.Match) -> str:
        key = match.group(1)
        return str(params.get(key, ""))

    return _VAR_PATTERN.sub(replace, raw)


async def send_email(email: EmailSchema) -> dict:
    """Render the named template with params and send via Brevo.

    Returns {"ok": bool, "status": int, ...}. Never raises on send failure
    — callers shouldn't lose the login flow because email is flaky.
    """
    try:
        html_content = _render(email.template_name, email.template_params)
    except Exception:
        logger.exception("Failed to render email template %s", email.template_name)
        return {"ok": False, "error": "template_error"}

    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json",
    }
    payload = {
        "sender": {
            "name": settings.BREVO_FROM_NAME,
            "email": settings.BREVO_FROM_EMAIL,
        },
        "to": [{"email": email.to_email}],
        "subject": email.subject,
        "htmlContent": html_content,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.BREVO_URL, json=payload, headers=headers)
    except Exception:
        logger.exception("Brevo request failed for %s", email.to_email)
        return {"ok": False, "error": "network_error"}

    if response.status_code not in (200, 201, 202):
        logger.error(
            "Brevo rejected email to %s: %s %s",
            email.to_email, response.status_code, response.text,
        )
        return {"ok": False, "status": response.status_code, "error": response.text}

    return {"ok": True, "status": response.status_code}