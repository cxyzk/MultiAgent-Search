from fastapi import APIRouter
from app.api.session import router as session_router
from app.api.chat import router as chat_router

api_router = APIRouter()
api_router.include_router(chat_router)
api_router.include_router(session_router)
