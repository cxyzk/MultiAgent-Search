"""知识库接口：文档上传 / 列表 / 详情 / 删除 + 检索调试"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.kb.retriever import bm25_retriever
from app.service.kb_service import kb_service
import os
from pydantic import BaseModel

router = APIRouter()

MAX_FILE_BYTES = 5 * 1024 * 1024   # 5MB 护栏：先让"太大"变成清晰失败


@router.post("/kb/documents")
async def upload_document(
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(None),
    content: str | None = Form(None),
    title: str | None = Form(None)
):
    """上传 txt/md 文件，或提交粘贴文本（二者给一个）"""
    if file is not None:
        raw = await file.read()
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(413, "文件超过 5MB")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "只支持 UTF-8 编码的文本文件")
        name = file.filename or  "未命名.txt"
        doc_title = title or os.path.splitext(os.path.basename(name))[0]
        source = name
    elif content:
        text = content
        doc_title = title or "粘贴文本"
        source = None
    else:
        raise HTTPException(400, "file 和 content 至少给一个")

    #去掉首位空白
    if not text.strip():
        raise HTTPException(400, "内容为空")
    return await kb_service.add_document(doc_title, text, db, source=source)



@router.get("/kb/documents")
async def list_documents(db: AsyncSession = Depends(get_db)):
    '''获取文档列表'''
    return await kb_service.list_documents(db)

@router.get("/kb/documents/{doc_id}")
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    '''获取文档详情'''
    doc = await kb_service.get_document(doc_id, db)
    if doc is None:
        raise HTTPException(404, "文档不存在")
    return doc


@router.delete("/kb/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    '''
    删除文档
    '''
    await kb_service.delete_document(doc_id, db)
    return {"ok": True}



class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

@router.post("/kb/search")
async def search_documents(req: SearchRequest):
     """检索调试：不经过 agent，直接看命中排序"""
     hits = await bm25_retriever.search(req.query, req.top_k)
     return {"query": req.query, "hits": hits}


