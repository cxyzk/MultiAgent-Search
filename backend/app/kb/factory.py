"""按配置选择检索器：BM25 / 向量 / 混合。"""
from app.core.config import settings
from app.kb.embedding_retriever import embedding_retriever
from app.kb.hybrid_retriever import HybridRetriever
from app.kb.retriever import bm25_retriever

_hybrid = HybridRetriever(bm25_retriever, embedding_retriever)


def get_retriever():
    mode = settings.retriever
    if mode == "embedding":
        return embedding_retriever
    if mode == "hybrid":
        return _hybrid
    return bm25_retriever
