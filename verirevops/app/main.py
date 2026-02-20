from fastapi import FastAPI, HTTPException, Depends
import asyncio
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.routers import admin, chatwoot, rag, health
from app.core.db import engine
from app.core.logger import Log
from app.models import Base
from app.core.exceptions import global_exception_handler, http_exception_handler
import alembic.config
import alembic.command
from concurrent.futures import ThreadPoolExecutor
@asynccontextmanager
async def lifespan(app: FastAPI):
    Log.info("Starting up VeriRevOps API...")

    Log.info("Starting up VeriRevOps API...")

    # Run Alembic migrations automatically
    try:
        alembic_cfg = alembic.config.Config("alembic.ini")

        # Run sync alembic command in a separate thread to avoid event loop conflict
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, alembic.command.upgrade, alembic_cfg, "head")

        Log.success("Database migrations applied successfully via Alembic.")
    except Exception as e:
        Log.error(f"Automatic migration failed: {e}")

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
