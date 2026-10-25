from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Currency(StrEnum):
    EUR = "EUR"
    MDL = "MDL"


class SellerType(StrEnum):
    OWNER = "owner"
    AGENCY = "agency"
    DEVELOPER = "developer"
    ANY = "any"


@dataclass(slots=True)
class SearchFilters:
    districts: set[str] = field(default_factory=lambda: {"Ботаника"})
    rooms: set[int] = field(default_factory=lambda: {1, 2})
    seller_types: set[SellerType] = field(default_factory=lambda: {SellerType.OWNER})
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    currency: Currency = Currency.EUR
    min_area: float | None = None
    max_area: float | None = None
    min_floor: int | None = None
    max_floor: int | None = None
    furnished: bool | None = None
    washing_machine: bool | None = None
    refrigerator: bool | None = None
    air_conditioner: bool | None = None
    internet: bool | None = None
    housing_stock: str | None = None


@dataclass(slots=True)
class Listing:
    external_id: str
    title: str
    url: str
    price: Decimal | None = None
    currency: str | None = None
    district: str | None = None
    address: str | None = None
    rooms: int | None = None
    area: float | None = None
    floor: int | None = None
    floors_total: int | None = None
    seller_type: str | None = None
    phone: str | None = None
    description: str | None = None
    image_urls: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    @property
    def main_image_url(self) -> str | None:
        return self.image_urls[0] if self.image_urls else None
