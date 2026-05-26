from fastapi import APIRouter, Depends, Request, Response

from sqlalchemy.orm import Session
from sqlalchemy import text
from redis.asyncio import Redis

from app.deps import get_redis, get_db
from app.services import auth
from app.schemas.auth import LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth")

@router.post("/login")
async def login(request: Request, response: Response, login_request: LoginRequest, db: Session = Depends(get_db), redis: Redis = Depends(get_redis)):
    result =  await auth.auth_flow(request, response, login_request, db, redis)
    return {"message": "This is test message."}

@router.post("/register")
async def register(response: Response, register_request: RegisterRequest, db: Session = Depends(get_db), redis: Redis = Depends(get_redis)):
    result =  await auth.register_flow(response, register_request, db, redis)
    return {"message": "This is test message."}