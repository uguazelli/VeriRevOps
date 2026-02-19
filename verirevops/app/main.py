from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.routers import admin, chatwoot, rag, health
from app.core.db import engine
from app.core.logger import Log
from app.models import Base
from app.core.exceptions import global_exception_handler, http_exception_handler

@asynccontextmanager
async def lifespan(app: FastAPI):
    Log.info("Starting up VeriRevOps API...")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield
    Log.info("Shutting down VeriRevOps API...")
    await engine.dispose()


app = FastAPI(
    title="VeriRevOps API",
    description="API for VeriRevOps with LangChain and Postgres VectorDB",
    version="0.1.0",
    lifespan=lifespan
)


app.include_router(health.router)
app.include_router(admin.router)
app.include_router(chatwoot.router)
app.include_router(rag.router)

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

app.mount("/admin", StaticFiles(directory="app/admin", html=True), name="admin")
