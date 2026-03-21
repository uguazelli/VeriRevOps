import httpx
import logging
from typing import Tuple
from fastapi import HTTPException

logger = logging.getLogger(__name__)

async def download_file_from_url(url: str) -> Tuple[bytes, str]:
    """
    Downloads a file from a given URL into memory.

    Returns:
        Tuple containing the file bytes and a suggested filename extracted from the URL or headers.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()

            # Try to get filename from Content-Disposition if available
            filename = "downloaded_file"
            content_disposition = response.headers.get("Content-Disposition")
            if content_disposition and "filename=" in content_disposition:
                # Basic extraction, e.g., attachment; filename="file.jpg"
                parts = content_disposition.split("filename=")
                if len(parts) > 1:
                    filename = parts[1].strip('"\'')
            else:
                # Try to extract from URL path
                path = url.split("?")[0]
                possible_name = path.split("/")[-1]
                if possible_name and "." in possible_name:
                    filename = possible_name

            return response.content, filename
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred while downloading: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch media from URL: {e}")
    except Exception as e:
        logger.error(f"Failed to download file from URL {url}: {e}")
        raise HTTPException(status_code=400, detail=f"Bad request or invalid URL: {str(e)}")
