from fastapi import APIRouter
from app.api.routes import router as routes_router


api_router = APIRouter()
api_router.include_router(routes_router)