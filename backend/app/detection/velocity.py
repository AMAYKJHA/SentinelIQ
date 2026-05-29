import secrets
import time

from redis.asyncio import Redis

from app.schemas.dto import VelocityResult
from app.core.config import settings


def _compute_risk(count: int, max_attempts: int) -> float:
    if max_attempts <= 0:
        return 0.0
    return min(count / (max_attempts * 2), 1.0)


async def check_velocity(user_id: int | None, ip: str, redis: Redis) -> VelocityResult:
    now = time.time()
    window_start = now - settings.VELOCITY_WINDOW_SECONDS

    user_key = f"velocity:user:{user_id}" if user_id is not None else None
    ip_key = f"velocity:ip:{ip}"
    user_ip_key = f"velocity:user_ip:{user_id}:{ip}" if user_id is not None else None

    pipe = redis.pipeline()
    if user_key:
        pipe.zremrangebyscore(user_key, "-inf", window_start)
    pipe.zremrangebyscore(ip_key, "-inf", window_start)
    if user_ip_key:
        pipe.zremrangebyscore(user_ip_key, "-inf", window_start)

    if user_key:
        pipe.zcard(user_key)
    pipe.zcard(ip_key)
    if user_ip_key:
        pipe.zcard(user_ip_key)

    results = await pipe.execute()

    # Pull counts out (depending on whether user_id was provided)
    if user_key:
        user_count = results[3]
        ip_count = results[4]
        user_ip_count = results[5]
    else:
        user_count = 0
        ip_count = results[1]
        user_ip_count = 0

    user_risk = _compute_risk(user_count, settings.USER_MAX_ATTEMPTS)
    ip_risk = _compute_risk(ip_count, settings.IP_MAX_ATTEMPTS)
    user_ip_risk = _compute_risk(user_ip_count, settings.USER_IP_MAX_ATTEMPTS)

    flagged = user_risk > 0.8 or ip_risk > 0.8 or user_ip_risk > 0.8

    return VelocityResult(
        user_count=user_count,
        ip_count=ip_count,
        user_ip_count=user_ip_count,
        user_risk=user_risk,
        ip_risk=ip_risk,
        user_ip_risk=user_ip_risk,
        flagged=flagged,
    )


async def record_attempt(user_id: int | None, ip: str, redis: Redis) -> None:
    now = time.time()
    # Unique suffix so multiple attempts in the same second don't collide as the
    # same ZSET member (which would silently undercount bursts).
    member = f"{now}:{secrets.token_hex(4)}"
    ip_key = f"velocity:ip:{ip}"
    pipe = redis.pipeline()
    pipe.zadd(ip_key, {member: now})
    pipe.expire(ip_key, settings.VELOCITY_WINDOW_SECONDS * 2)

    if user_id is not None:
        user_key = f"velocity:user:{user_id}"
        user_ip_key = f"velocity:user_ip:{user_id}:{ip}"
        pipe.zadd(user_key, {member: now})
        pipe.expire(user_key, settings.VELOCITY_WINDOW_SECONDS * 2)
        pipe.zadd(user_ip_key, {member: now})
        pipe.expire(user_ip_key, settings.VELOCITY_WINDOW_SECONDS * 2)

    await pipe.execute()