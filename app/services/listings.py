from __future__ import annotations

from app.database.models import Filter, Listing
from app.database.repository import Repository
from app.parser.parser import ListingParser


class ListingsService:
    def __init__(self, parser: ListingParser, repository: Repository) -> None:
        self.parser = parser
        self.repository = repository

    async def search(self, record: Filter) -> list[Listing]:
        parsed = await self.parser.search(self.repository.to_search_filter(record))
        return [await self.repository.upsert_listing(item) for item in parsed]
