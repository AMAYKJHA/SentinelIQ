from fastapi import APIRouter, Depends
from fastapi.requests import Request

from redis.asyncio import Redis

from app.deps import get_redis
from app.detection.velocity import check_velocity

router = APIRouter()

@router.get("/login")
async def login(request: Request, user_id: int, redis: Redis = Depends(get_redis)):
    ip = request.client.host
    result = await check_velocity(user_id, ip, redis)
    return {"result": result}