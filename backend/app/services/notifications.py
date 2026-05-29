"""High-level email notifications wrapping send_email.

All functions swallow errors — auth flow must never fail because email failed.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.dto import EmailSchema
from app.services.email import send_email

logger = logging.getLogger(__name__)


def _fire_and_forget(coro) -> None:
    """Run an awaitable in the background without blocking the caller."""
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        # no running loop — caller is sync. Just drop it.
        logger.warning("Could not schedule notification: no event loop")


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _map_link(lat: float | None, lon: float | None, city: str, country: str) -> str | None:
    """Build a Google Maps link from coordinates, falling back to a text query.
    Returns None when we have nothing to point at."""
    if lat is not None and lon is not None:
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    label = ", ".join(p for p in (city, country) if p)
    if label:
        from urllib.parse import quote
        return f"https://www.google.com/maps/search/?api=1&query={quote(label)}"
    return None


def _map_html(lat: float | None, lon: float | None, city: str, country: str) -> str:
    link = _map_link(lat, lon, city, country)
    if not link:
        return ""
    return (
        ' &middot; '
        f'<a href="{link}" style="color:#2563eb;text-decoration:none">'
        'View on map &rarr;</a>'
    )


async def send_register_otp(email: str, name: str, otp: str) -> dict:
    return await send_email(EmailSchema(
        to_email=email,
        subject=f"Verify your {settings.APP_NAME} account",
        template_name="register.html",
        template_params={
            "app_name": settings.APP_NAME,
            "name": name or "there",
            "otp_code": otp,
            "expiry_minutes": settings.OTP_TTL_SECONDS // 60,
        },
    ))


async def send_mfa_otp(email: str, name: str, otp: str) -> dict:
    return await send_email(EmailSchema(
        to_email=email,
        subject=f"{settings.APP_NAME} verification code: {otp}",
        template_name="mfa.html",
        template_params={
            "name": name or "there",
            "otp_code": otp,
            "expiry_minutes": settings.OTP_TTL_SECONDS // 60,
        },
    ))


def notify_suspicious_login(
    email: str, name: str, ip: str, city: str, country: str, device: str,
    yes_token: str, no_token: str,
    lat: float | None = None, lon: float | None = None,
) -> None:
    yes_link = f"{settings.FRONTEND_BASE_URL}/security/confirm?token={yes_token}"
    no_link = f"{settings.FRONTEND_BASE_URL}/security/deny?token={no_token}"
    _fire_and_forget(send_email(EmailSchema(
        to_email=email,
        subject=f"Suspicious sign-in to your {settings.APP_NAME} account",
        template_name="was_it_you.html",
        template_params={
            "app_name": settings.APP_NAME,
            "name": name or "there",
            "ip": ip,
            "city": city or "Unknown",
            "country": country or "Unknown",
            "map_link": _map_link(lat, lon, city, country),
            "map_html": _map_html(lat, lon, city, country),
            "login_time": _now_str(),
            "yes_link": yes_link,
            "no_link": no_link,
        },
    )))


def notify_new_device(
    email: str, name: str, ip: str, city: str, country: str, device: str,
    wasnt_me_token: str,
    lat: float | None = None, lon: float | None = None,
) -> None:
    wasnt_me_link = f"{settings.FRONTEND_BASE_URL}/security/deny?token={wasnt_me_token}"
    _fire_and_forget(send_email(EmailSchema(
        to_email=email,
        subject=f"New device signed in to {settings.APP_NAME}",
        template_name="new_device.html",
        template_params={
            "app_name": settings.APP_NAME,
            "name": name or "there",
            "ip": ip,
            "city": city or "Unknown",
            "country": country or "Unknown",
            "map_link": _map_link(lat, lon, city, country),
            "map_html": _map_html(lat, lon, city, country),
            "device": device or "Unknown",
            "login_time": _now_str(),
            "wasnt_me_link": wasnt_me_link,
        },
    )))
