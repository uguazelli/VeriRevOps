from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    VERIDATA_SYNC_PORT: int = 8001
    ADMIN_USER: str = "admin"
    ADMIN_PASSWORD: str = "admin"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
