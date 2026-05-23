import time

from redis.asyncio import Redis

from app.schemas.dto import VelocityResult
from app.core.config import settings

def _compute_risk(count: int, max_attempts: int) -> float:
    return min(count / (max_attempts * 2), 1.0)

async def check_velocity(
    user_id: int, ip: str,
    redis: Redis
    ) -> VelocityResult:
    
    now =time.time()
    window_start = now - settings.VELOCITY_WINDOW_SECONDS
    
    user_key = f"velocity:user:{user_id}"
    ip_key = f"velocity:ip:{ip}"
    
    pipe = redis.pipeline()
    
    pipe.zremrangebyscore(user_key, "-inf", window_start)
    pipe.zremrangebyscore(ip_key, "-inf", window_start)
    
    pipe.zadd(user_key, {str(now): now})
    pipe.zadd(ip_key, {str(now): now})
    
    pipe.zcard(user_key)
    pipe.zcard(ip_key)
    
    pipe.expire(user_key, settings.VELOCITY_WINDOW_SECONDS * 2)
    pipe.expire(ip_key, settings.VELOCITY_WINDOW_SECONDS * 2)
    
    results = await pipe.execute()
    
    user_count = results[4]
    ip_count = results[5]
    
    user_risk = _compute_risk(user_count, settings.USER_MAX_ATTEMPTS)
    ip_risk = _compute_risk(ip_count, settings.IP_MAX_ATTEMPTS)
    
    combined_risk = (user_risk * 0.7) + (ip_risk * 0.3)
    
    flagged = (
        user_count > settings.USER_MAX_ATTEMPTS
        or ip_count > settings.IP_MAX_ATTEMPTS
    )
    
    return VelocityResult(
        user_count=user_count,
        ip_count=ip_count,
        user_risk=user_risk,
        ip_risk=ip_risk,
        combined_risk=round(combined_risk, 4),
        flagged=flagged,
    )   
    
    