import time

from redis.asyncio import Redis

from app.schemas.dto import VelocityResult
from app.core.config import settings

def _compute_risk(count: int, max_attempts: int) -> float:
    return min(count / (max_attempts * 2), 1.0)

async def check_velocity(user_id: int, ip: str, redis: Redis) -> VelocityResult:
    now = time.time()
    window_start = now - settings.VELOCITY_WINDOW_SECONDS

    user_key = f"velocity:user:{user_id}"
    ip_key = f"velocity:ip:{ip}"

    pipe = redis.pipeline()

    # clean expired entries
    pipe.zremrangebyscore(user_key, "-inf", window_start)
    pipe.zremrangebyscore(ip_key, "-inf", window_start)

    # read current counts BEFORE adding this attempt
    pipe.zcard(user_key)
    pipe.zcard(ip_key)

    results = await pipe.execute()

    user_count = results[2]
    ip_count = results[3]

    user_risk = _compute_risk(user_count, settings.USER_MAX_ATTEMPTS)
    ip_risk = _compute_risk(ip_count, settings.IP_MAX_ATTEMPTS)
    flagged = user_risk > 0.8 or ip_risk > 0.8

    return VelocityResult(
        user_count=user_count,
        ip_count=ip_count,
        user_risk=user_risk,
        ip_risk=ip_risk,
        flagged=flagged,
    )


async def record_attempt(user_id: int | None, ip: str, redis: Redis) -> None:
    now = time.time()
    user_key = f"velocity:user:{user_id}"
    ip_key = f"velocity:ip:{ip}"

    pipe = redis.pipeline()
    if user_id is not None:
        pipe.zadd(user_key, {str(now): now})
        pipe.expire(user_key, settings.VELOCITY_WINDOW_SECONDS * 2)

    pipe.zadd(ip_key, {str(now): now})
    pipe.expire(ip_key, settings.VELOCITY_WINDOW_SECONDS * 2)
    await pipe.execute()