from app.kb.retriever import tokenize


def test_tokenize_mixed_language():
    toks = tokenize("用 asyncio 控制并发")
    assert "asyncio" in toks
    assert "并发" in toks
