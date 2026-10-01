from pydantic_settings import BaseSettings,SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config =SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore")
    llm_base_url: str
    llm_api_key: str
    llm_model:str


@lru_cache
def get_settings():
    return Settings()
settings = get_settings()


