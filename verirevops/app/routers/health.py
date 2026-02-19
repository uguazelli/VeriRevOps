from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.core.db import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
def health_check():
    return {"status": "ok", "message": "VeriRevOps API is running"}


@router.get("/db")
async def health_check_db():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")