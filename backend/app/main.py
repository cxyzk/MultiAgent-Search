from fastapi import  FastAPI
from app.api.routes import router

app=FastAPI(title="MultiAgent-Search")

@app.get("/health")
async def health():
    return {"status": "ok"}
app.include_router(router,prefix="/api")




