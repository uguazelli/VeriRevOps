from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.routers import admin, chatwoot, rag, health
from app.core.db import engine, get_db
from app.core.logger import Log
from app.models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    Log.info("Starting up VeriRevOps API...")

    async with engine.begin() as conn:
        # Create extension if not exists (needs superuser or proper permissions)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create tables
        await conn.run_sync(Base.metadata.create_all)

    yield
    # Shutdown logic
    Log.info("Shutting down VeriRevOps API...")
    await engine.dispose()


app = FastAPI(
    title="VeriRevOps API",
    description="API for VeriRevOps with LangChain and Postgres VectorDB",
    version="0.1.0",
    lifespan=lifespan
)

from app.core.exceptions import global_exception_handler, http_exception_handler
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

app.include_router(health.router)
app.include_router(admin.router)
app.include_router(chatwoot.router)
app.include_router(rag.router)

app.mount("/admin", StaticFiles(directory="app/admin", html=True), name="admin")
