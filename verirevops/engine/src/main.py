import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.core.db import init_db, close_pool
from src.core.admin import setup_admin
from src.core.logging import setup_logging
from src.modules.admin_ui.router import router as admin_ui_router
from src.modules.ai.router import router as ai_router
from src.modules.chatwoot.router import router as chatwoot_router
from src.modules.conversation_summary.router import router as conversation_summary_router
from src.modules.contact_sync.router import router as contact_sync_router
from src.modules.global_config.router import router as global_config_router
from src.modules.rag.router import router as rag_router
from src.modules.tenants.router import router as tenants_router

# Setup Logging
setup_logging()
logger = logging.getLogger(__name__)

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    close_pool()

app = FastAPI(title="VeriRag Core", lifespan=lifespan)

# Custom ASGI Middleware to force HTTPS scheme when behind proxies
# that strip or misconfigure X-Forwarded-Proto (like APISIX/Cloudflare)
class ForceHTTPSMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            host = headers.get(b"host", b"").decode("latin-1")

            # If accessed via a public domain (not local dev), force HTTPS
            if "localhost" not in host and "127.0.0.1" not in host:
                scope["scheme"] = "https"

        await self.app(scope, receive, send)

app.add_middleware(ForceHTTPSMiddleware)

# Setup SQLAdmin
setup_admin(app)

# Include Routers
# Admin UI Router - Mounts at root
app.include_router(admin_ui_router)

# AI Router - Mounts at /api
app.include_router(ai_router, prefix="/api")

# RAG Router - Mounts at /api
app.include_router(rag_router, prefix="/api")

# Chatwoot Router - Mounts at /api
app.include_router(chatwoot_router, prefix="/api")

# Conversation Summary Router - Mounts at /api
app.include_router(conversation_summary_router, prefix="/api")

# Contact Sync Router - Mounts at /api
app.include_router(contact_sync_router, prefix="/api")

# Global Config Router - Mounts at /api
app.include_router(global_config_router, prefix="/api")

# Tenants Router - Mounts at /api
app.include_router(tenants_router, prefix="/api")

# Static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")
