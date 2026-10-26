"""按配置选择检索器：BM25 / 向量 / 混合，可再包一层 rerank（两阶段）。"""
from app.core.config import settings
from app.kb.embedding_retriever import embedding_retriever
from app.kb.hybrid_retriever import HybridRetriever
from app.kb.reranked_retriever import RerankedRetriever
from app.kb.retriever import bm25_retriever

_hybrid = HybridRetriever(bm25_retriever, embedding_retriever)


def _base_retriever():
    mode = settings.retriever
    if mode == "embedding":
        return embedding_retriever
    if mode == "hybrid":
        return _hybrid
    return bm25_retriever


def get_retriever():
    base = _base_retriever()
    # rerank 走硅基流动，和 embedding 共用同一个 key
    if settings.rerank_enabled and settings.embedding_api_key:
        return RerankedRetriever(base)
    return base
