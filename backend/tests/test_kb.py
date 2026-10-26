import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_then_search(client):
    files = {"file": ("note.md",
                      "向量数据库在十万条以内用暴力检索就足够，百万级才需要 ANN 索引。".encode("utf-8"),
                      "text/markdown")}
    resp = await client.post("/api/kb/documents", files=files, data={"title": "检索笔记"})
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["chunks"] >= 1

    resp = await client.post("/api/kb/search", json={"query": "暴力检索", "top_k": 1})
    hits = resp.json()["hits"]
    assert hits and "暴力检索" in hits[0]["content"]


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_rejects_empty(client):
    files = {"file": ("empty.md", b"", "text/markdown")}
    resp = await client.post("/api/kb/documents", files=files)
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_html_converts_to_markdown(client):
    """HTML 上传：标题转 Markdown 标题、代码块转围栏，chunker 才能识别结构。"""
    html = (
        "<html><body>"
        "<h1>设计模式</h1>"
        "<p>单例模式保证全局唯一实例。</p>"
        "<pre><code>class Singleton:\n    pass</code></pre>"
        "</body></html>"
    )
    files = {"file": ("note.html", html.encode("utf-8"), "text/html")}
    resp = await client.post("/api/kb/documents", files=files)
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["chunks"] >= 1

    detail = await client.get(f"/api/kb/documents/{doc['id']}")
    content = "\n".join(chunk["content"] for chunk in detail.json()["chunks"])
    assert "设计模式" in content          # 正文保留
    assert "```" in content               # 代码围栏保护住
