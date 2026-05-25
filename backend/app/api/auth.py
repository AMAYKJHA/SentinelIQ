from fastapi import APIRouter, Depends
from fastapi.requests import Request

from redis.asyncio import Redis

from app.deps import get_redis
from app.detection.velocity import check_velocity
from app.schemas.auth import LoginRequest

router = APIRouter()

@router.post("/login")
async def login(request: Request, login_request: LoginRequest, redis: Redis = Depends(get_redis)):
    ip = request.client.host
    # result = await check_velocity(login_request.credentials.email, ip, redis)
    return {"result": "Test"}