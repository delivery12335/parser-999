from __future__ import annotations

import re

from app.config import Settings
from app.database.models import Call, Listing, User
from app.database.repository import Repository


class CallService:
    def __init__(self, repository: Repository, settings: Settings) -> None:
        self.repository = repository
        self.mode = settings.call_mode

    async def _authorized_listing(self, telegram_id: int, listing_id: int) -> tuple[User, Listing, str]:
        if not await self.repository.is_owner(telegram_id):
            raise PermissionError("Calls are restricted to the configured Telegram account")
        user, _ = await self.repository.get_filter(telegram_id)
        listing = await self.repository.listing(listing_id)
        if not listing or not listing.phone:
            raise ValueError("Listing has no public phone")
        phone = re.sub(r"[^\d+]", "", listing.phone)
        if not re.fullmatch(r"\+373\d{8}", phone):
            raise ValueError("Only normalized Moldovan phone numbers are accepted")
        return user, listing, phone

    async def request(self, telegram_id: int, listing_id: int) -> Call:
        user, listing, phone = await self._authorized_listing(telegram_id, listing_id)
        return await self.repository.create_call(user.id, listing.id, phone)

    async def present_on_iphone(self, telegram_id: int, listing_id: int) -> tuple[Listing, Call]:
        user, listing, phone = await self._authorized_listing(telegram_id, listing_id)
        call = await self.repository.create_call(user.id, listing.id, phone, status="presented")
        return listing, call
