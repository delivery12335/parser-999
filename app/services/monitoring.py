from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.bot.sender import send_listing
from app.database.repository import Repository
from app.parser.parser import ParserBlockedError
from app.services.images import ImageService
from app.services.listings import ListingsService

logger = logging.getLogger(__name__)


class Monitor:
    def __init__(self, bot: Bot, repository: Repository, listings: ListingsService, images: ImageService, interval: int) -> None:
        self.bot = bot
        self.repository = repository
        self.listings = listings
        self.images = images
        self.interval = interval
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.check_once()
            except ParserBlockedError as exc:
                logger.warning("Monitoring paused for this cycle: %s", exc)
            except Exception:
                logger.exception("Monitoring cycle failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except TimeoutError:
                pass

    async def check_once(self) -> None:
        for user, record in await self.repository.monitoring_users():
            try:
                found = await self.listings.search(record)
                for listing in reversed(found):
                    if not await self.repository.unseen(user.id, listing.id):
                        continue
                    await send_listing(self.bot, user.telegram_id, listing, self.images, fresh=True)
                    await self.repository.mark_sent(user.id, listing.id)
            except ParserBlockedError:
                raise
            except Exception:
                logger.exception("Monitoring failed for Telegram user %s", user.telegram_id)
