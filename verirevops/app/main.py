
from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.routers import admin, chatwoot, rag
from app.core.db import engine, get_db
from app.models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Starting up VeriRevOps API...")

    async with engine.begin() as conn:
        # Create extension if not exists (needs superuser or proper permissions)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create tables
        await conn.run_sync(Base.metadata.create_all)

    yield
    # Shutdown logic
    print("Shutting down VeriRevOps API...")
    await engine.dispose()


app = FastAPI(
    title="VeriRevOps API",
    description="API for VeriRevOps with LangChain and Postgres VectorDB",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(admin.router)
app.include_router(chatwoot.router)
app.include_router(rag.router)

app.mount("/admin", StaticFiles(directory="app/admin", html=True), name="admin")


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "VeriRevOps API is running"}

@app.get("/health/db")
async def health_check_db():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")
