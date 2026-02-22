import asyncio
from functools import wraps
from typing import Any, Callable, Type, Tuple, Optional, Union
from app.core.logger import Log

def with_retries(
    attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
    log_message: str = "Operation failed, retrying..."
):
    """
    Decorator that retries an async function with exponential backoff.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == attempts - 1:
                        Log.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise

                    Log.warning(f"{log_message} (Attempt {attempt + 1}/{attempts}). Error: {e}")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            return None # Should not be reachable due to raise above
        return wrapper
    return decorator

def log_and_ignore(
    default_return: Any = None,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
    log_level: str = "error"
):
    """
    Decorator that logs an exception and returns a default value instead of raising.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                log_func = getattr(Log, log_level, Log.error)
                log_func(f"Error in {func.__name__} (ignoring): {e}")
                return default_return
        return wrapper
    return decorator
