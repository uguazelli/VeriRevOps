from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from app.db import init_db_pool, close_db_pool
from app.init_db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()  # Auto-run migrations/schema
    await init_db_pool()
    yield
    # Shutdown
    await close_db_pool()

from app.auth import verify_credentials
from fastapi import Depends

app = FastAPI(title="Veridata Sync", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

from app.routes import tenants, configs, contacts, api
app.include_router(tenants.router)
app.include_router(configs.router)
app.include_router(contacts.router)
app.include_router(api.router)

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/tenants")
