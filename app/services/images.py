from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


class ImageService:
    def __init__(self, timeout: float = 20.0) -> None:
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def close(self) -> None:
        await self.client.aclose()

    @asynccontextmanager
    async def downloaded(self, url: str) -> AsyncIterator[str]:
        path = ""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            suffix = ".jpg"
            content_type = response.headers.get("content-type", "")
            if "png" in content_type:
                suffix = ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                handle.write(response.content)
                path = handle.name
            yield path
        finally:
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
