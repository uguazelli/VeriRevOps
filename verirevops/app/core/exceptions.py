import traceback
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.core.logger import Log

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

async def global_exception_handler(request: Request, exc: Exception):
    # Catches all unhandled exceptions, logs them, and returns a 500 response.
    Log.error(f"Unhandled error at {request.url.path}: {exc}")
    traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    # Handles FastAPI HTTPExceptions (like 404, 400).
    Log.warning(f"HTTP {exc.status_code} at {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    # Handles general SQLAlchemy errors.
    Log.error(f"Database error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred."}
    )

async def integrity_exception_handler(request: Request, exc: IntegrityError):
    # Handles database integrity errors (e.g., unique constraint violations).
    Log.warning(f"Database integrity error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": "Database integrity violation. Please check your input."}
    )
