from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from app.core.database import check_db_connection, create_database_if_not_exists, create_tables_if_not_exist
from app.controller import handle_webhook

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Starting up VeriRevOps API...")
    create_database_if_not_exists()
    create_tables_if_not_exist()
    yield
    # Shutdown logic
    print("Shutting down VeriRevOps API...")

from fastapi.staticfiles import StaticFiles
from app.routers import admin

app = FastAPI(
    title="VeriRevOps API",
    description="API for VeriRevOps with LangChain and Postgres VectorDB",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(admin.router)

# Mount the admin directory as static files
app.mount("/admin", StaticFiles(directory="app/admin", html=True), name="admin")

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "VeriRevOps API is running"}

@app.get("/health/db")
async def health_check_db():
    success, message = check_db_connection()
    if success:
        return {"status": "ok", "message": message}
    else:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {message}")

@app.post("/webhook/{alias}")
async def webhook(alias: str, webhook_data: dict):
    return handle_webhook(alias, webhook_data)
