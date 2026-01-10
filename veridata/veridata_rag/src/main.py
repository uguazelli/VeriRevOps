import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.db import init_db, close_pool
from src.controllers import web, api, ops
from src.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    close_pool()

app = FastAPI(title="VeriRag Core", lifespan=lifespan)

app.include_router(web.router)
app.include_router(api.router, prefix="/api")
app.include_router(ops.router, prefix="/ops", tags=["ops"])
app.mount("/static", StaticFiles(directory="src/static"), name="static")
