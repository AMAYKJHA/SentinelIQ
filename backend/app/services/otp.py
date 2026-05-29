"""Redis-backed OTP storage and verification.

Stores hashed OTPs. Tracks attempt count to prevent brute force.
"""
import hashlib
import hmac
import secrets

from redis.asyncio import Redis

from app.core.config import settings


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def _key(purpose: str, subject: str) -> str:
    # purpose: "register", "mfa". subject: email or challenge_id
    return f"otp:{purpose}:{subject}"


def generate_otp() -> str:
    n = settings.OTP_LENGTH
    return f"{secrets.randbelow(10 ** n):0{n}d}"


async def issue_otp(redis: Redis, purpose: str, subject: str) -> str:
    """Generate, store (hashed) and return the plaintext OTP."""
    otp = generate_otp()
    key = _key(purpose, subject)
    pipe = redis.pipeline()
    pipe.hset(key, mapping={"hash": _hash_otp(otp), "attempts": 0})
    pipe.expire(key, settings.OTP_TTL_SECONDS)
    await pipe.execute()
    return otp


async def verify_otp(redis: Redis, purpose: str, subject: str, otp: str) -> tuple[bool, str]:
    """Returns (ok, reason). On success consumes the OTP."""
    key = _key(purpose, subject)
    data = await redis.hgetall(key)
    if not data:
        return False, "expired_or_missing"

    attempts = int(data.get("attempts", 0))
    if attempts >= settings.OTP_MAX_ATTEMPTS:
        await redis.delete(key)
        return False, "too_many_attempts"

    if not hmac.compare_digest(data.get("hash", ""), _hash_otp(otp)):
        await redis.hincrby(key, "attempts", 1)
        return False, "invalid"

    await redis.delete(key)
    return True, "ok"
