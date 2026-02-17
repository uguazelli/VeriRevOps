import logging
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from bot.core.config import settings
from bot.api.endpoints import router as api_router
from bot.bot.engine import process_bot_event, process_integration_event
from bot.core.db import async_session_maker, engine
from bot.core.logging import setup_logging
from rag.controllers.api import router as rag_api_router
from admin import (
    BotSessionAdmin,
    ClientAdmin,
    ClientConfigAdmin,
    DocumentAdmin,
    GlobalConfigAdmin,
    SubscriptionAdmin,
    SyncConfigAdmin,
    views_rag,
    authentication_backend,
)


setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Veridata Bot")

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.include_router(api_router, prefix="/api/v1")
app.mount("/admin-rag/static", StaticFiles(directory="rag/static"), name="rag-static")
app.include_router(rag_api_router, prefix="/api/v1/rag", tags=["RAG"])
app.include_router(views_rag.router, prefix="/admin-rag", tags=["RAG-UI"])

admin = Admin(
    app,
    engine,
    authentication_backend=authentication_backend,
    title="VeriBot Admin",
    base_url="/admin-bot",
    logo_url="/admin-rag/static/logo.png", # Reusing RAG static map
    templates_dir="admin/templates",
)


admin.add_view(ClientAdmin)
admin.add_view(SyncConfigAdmin)
admin.add_view(ClientConfigAdmin)
admin.add_view(SubscriptionAdmin)
admin.add_view(BotSessionAdmin)
admin.add_view(GlobalConfigAdmin)
admin.add_view(DocumentAdmin)


async def run_bot_bg(client_slug: str, payload: dict):
    async with async_session_maker() as db:
        await process_bot_event(client_slug, payload, db)


async def run_integration_bg(client_slug: str, payload: dict):
    async with async_session_maker() as db:
        await process_integration_event(client_slug, payload, db)


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Veridata Bot Running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/bot/chatwoot/{client_slug}")
async def chatwoot_bot_handler(client_slug: str, request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(run_bot_bg, client_slug, payload)
    return {"status": "processing_started"}


@app.post("/integrations/chatwoot/{client_slug}")
async def chatwoot_integration_handler(client_slug: str, request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(run_integration_bg, client_slug, payload)
    return {"status": "processing_started"}
