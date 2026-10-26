from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore")
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    tavily_api_key: str = ""
    db_url: str

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    retriever: str = "bm25"

    # Rerank：两阶段检索的第二段（先多召回，再精排）
    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # 查询改写：口语化问题 → 1~3 条检索式（需要一次 LLM 调用）
    query_rewrite_enabled: bool = False

    @property
    def enable_web_search(self) -> bool:
        return bool(self.tavily_api_key)


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
