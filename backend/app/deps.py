from fastapi import Depends, HTTPException, Cookie

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.db.session import SessionLocal
from app.core.security import decode_token
from app.db.models import User
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def is_authenticated(access_token: str | None = Cookie(default=None)):
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access token")

    payload = decode_token(access_token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

async def get_current_user(payload: dict = Depends(is_authenticated), db: AsyncSession = Depends(get_db)): 
    stmt = select(User).where(User.uuid == payload.get("sub"))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user