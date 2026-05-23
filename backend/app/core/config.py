from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )
    
    DEBUG: bool = True
    DATABASE_URL: str
    SECRET_KEY: str = "unsafe-KOACG1Y8u-Y_akeSco4nrSshIPAf3Xxhs9ZKU"
    
    ALGORITHM: str ="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60*24
    
    ALLOW_ORIGINS: list[str] = ["*"]

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    
    VELOCITY_WINDOW_SECONDS: int = 60
    USER_MAX_ATTEMPTS: int = 5
    IP_MAX_ATTEMPTS: int = 20
    VELOCITY_WEIGHT: float = 0.4
           
    
settings = Settings()