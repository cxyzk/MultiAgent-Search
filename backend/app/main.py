from fastapi import  FastAPI
from app.api import api_router

app=FastAPI(title="MultiAgent-Search")

@app.get("/health")
async def health():
    return {"status": "ok"}
app.include_router(api_router,prefix="/api")




