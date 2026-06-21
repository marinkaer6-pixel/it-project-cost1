from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./it_project.db"
    TELEGRAM_BOT_TOKEN: str = ""
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()