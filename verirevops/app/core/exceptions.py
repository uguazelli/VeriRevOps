from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.core.logger import Log

async def global_exception_handler(request: Request, exc: Exception):
    # Catches all unhandled exceptions, logs them, and returns a 500 response.
    Log.error(f"Unhandled error at {request.url.path}: {exc}")
    import traceback
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
