"""MFA pending-login challenges and was-it-you / wasnt-me magic links.

Both stored in Redis with TTL. Challenges contain the data needed to resume
the login after OTP success (user_id, device_id, ip, risk, etc.).
"""
import json
import secrets
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings


def _challenge_key(challenge_id: str) -> str:
    return f"mfa:challenge:{challenge_id}"


def _magic_key(token: str) -> str:
    return f"magic:{token}"


async def create_challenge(redis: Redis, payload: dict[str, Any]) -> str:
    challenge_id = secrets.token_urlsafe(24)
    await redis.set(
        _challenge_key(challenge_id),
        json.dumps(payload),
        ex=settings.MFA_CHALLENGE_TTL_SECONDS,
    )
    return challenge_id


async def load_challenge(redis: Redis, challenge_id: str) -> dict | None:
    raw = await redis.get(_challenge_key(challenge_id))
    if not raw:
        return None
    return json.loads(raw)


async def consume_challenge(redis: Redis, challenge_id: str) -> None:
    await redis.delete(_challenge_key(challenge_id))


async def create_magic_link(redis: Redis, payload: dict[str, Any]) -> str:
    """Used for both 'yes it was me' and 'no it wasn't' confirmation links.

    payload should include {"kind": "yes"|"no", "user_id": ..., "event_id": ..., "device_id": ...}
    """
    token = secrets.token_urlsafe(32)
    await redis.set(
        _magic_key(token),
        json.dumps(payload),
        ex=settings.MAGIC_LINK_TTL_SECONDS,
    )
    return token


async def consume_magic_link(redis: Redis, token: str) -> dict | None:
    raw = await redis.get(_magic_key(token))
    if not raw:
        return None
    await redis.delete(_magic_key(token))
    return json.loads(raw)
