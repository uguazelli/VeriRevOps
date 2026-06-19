import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.core.admin import setup_admin
from src.core.db import close_pool, init_db
from src.core.logging import setup_logging
from src.modules.admin_ui.router import router as admin_ui_router
from src.modules.ai.router import router as ai_router
from src.modules.auth.router import router as auth_router
from src.modules.chatwoot.router import router as chatwoot_router
from src.modules.contact_sync.router import router as contact_sync_router
from src.modules.conversation_summary.router import router as conversation_summary_router
from src.modules.global_config.router import router as global_config_router
from src.modules.rag.router import router as rag_router
from src.modules.tenants.router import router as tenants_router

setup_logging()
logger = logging.getLogger(__name__)


def _bootstrap_superadmin():
    """Create the initial superadmin user from env vars if none exists yet."""
    import psycopg
    from src.core.security import hash_password

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return

    db_url_sync = db_url.replace("postgresql+psycopg://", "postgresql://", 1)

    email = os.getenv("SUPERADMIN_EMAIL") or os.getenv("ADMIN_EMAIL")
    if not email:
        admin_user = os.getenv("ADMIN_USER", "admin")
        email = f"{admin_user}@admin.local"

    password = os.getenv("SUPERADMIN_PASSWORD", "admin")

    try:
        with psycopg.connect(conninfo=db_url_sync) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE role = 'superadmin' LIMIT 1")
                row = cur.fetchone()
                hashed = hash_password(password)
                if row is None:
                    cur.execute(
                        "INSERT INTO users (email, hashed_password, role, is_active) VALUES (%s, %s, %s, %s)",
                        [email.lower(), hashed, "superadmin", True],
                    )
                    logger.info("Superadmin created: %s", email)
                else:
                    cur.execute(
                        "UPDATE users SET email = %s, hashed_password = %s WHERE id = %s",
                        [email.lower(), hashed, row[0]],
                    )
                    logger.info("Superadmin credentials synced: %s", email)
                conn.commit()
    except Exception as exc:
        logger.error("Superadmin bootstrap failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _bootstrap_superadmin()
    yield
    close_pool()


app = FastAPI(title="VeriRag Core", lifespan=lifespan)


class ForceHTTPSMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            host = headers.get(b"host", b"").decode("latin-1")
            if "localhost" not in host and "127.0.0.1" not in host:
                scope["scheme"] = "https"
        await self.app(scope, receive, send)


app.add_middleware(ForceHTTPSMiddleware)

setup_admin(app)

# Auth router (register, login, logout, invite) — no prefix
app.include_router(auth_router)

# Admin UI router (dashboard, tenant management) — no prefix
app.include_router(admin_ui_router)

# API routers
app.include_router(ai_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(chatwoot_router, prefix="/api")
app.include_router(conversation_summary_router, prefix="/api")
app.include_router(contact_sync_router, prefix="/api")
app.include_router(global_config_router, prefix="/api")
app.include_router(tenants_router, prefix="/api")

app.mount("/static", StaticFiles(directory="src/static"), name="static")
