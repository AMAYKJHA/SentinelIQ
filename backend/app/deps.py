from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Redis | None = None

def get_redis_client() -> Redis:
    global _redis_client
    
    if _redis_client is None:
        _redis_client = Redis(
            host = settings.REDIS_HOST,
            port = settings.REDIS_PORT,
            password = settings.REDIS_PASSWORD,
            ssl = True,
            decode_responses = True
        )
    return _redis_client

async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
    
    
async def get_redis():
    yield get_redis_client()
