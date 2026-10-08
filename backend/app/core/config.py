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
    tavily_api_key: str = ""
    db_url: str

    @property
    def enable_web_search(self) -> bool:
        return bool(self.tavily_api_key)


@lru_cache
def get_settings():
    return Settings()
settings = get_settings()


