import logging

import httpx
from fastapi import HTTPException


logger = logging.getLogger(__name__)


async def download_file_from_url(url: str) -> tuple[bytes, str]:
    """
    Download a file from a URL and return bytes plus a best-effort filename.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()

            return response.content, get_download_filename(url, response.headers)
    except httpx.HTTPStatusError as exc:
        logger.error("HTTP error while downloading media: %s", exc)
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Failed to fetch media from URL: {exc}",
        ) from exc
    except Exception as exc:
        logger.error("Failed to download file from URL %s: %s", url, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Bad request or invalid URL: {exc}",
        ) from exc


def get_download_filename(url: str, headers) -> str:
    content_disposition = headers.get("Content-Disposition")

    if content_disposition and "filename=" in content_disposition:
        parts = content_disposition.split("filename=")
        if len(parts) > 1:
            return parts[1].strip('"\'')

    path = url.split("?")[0]
    possible_name = path.split("/")[-1]

    if possible_name and "." in possible_name:
        return possible_name

    return "downloaded_file"
