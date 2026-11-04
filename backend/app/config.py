import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./ustaz_dev.db"
    admin_secret: str = "CHANGE_ME"
    app_secret: str = "CHANGE_ME"
    public_base_url: str = "http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
