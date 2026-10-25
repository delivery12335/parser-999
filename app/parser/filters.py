from __future__ import annotations

from decimal import Decimal

from app.parser.models import Currency, Listing, SearchFilters, SellerType


def matches_filters(listing: Listing, filters: SearchFilters) -> bool:
    if filters.districts and listing.district not in filters.districts:
        return False
    if filters.rooms and listing.rooms not in filters.rooms:
        return False
    if filters.seller_types and SellerType.ANY not in filters.seller_types:
        if listing.seller_type not in {value.value for value in filters.seller_types}:
            return False
    if listing.price is not None and listing.currency == filters.currency.value:
        price = Decimal(listing.price)
        if filters.min_price is not None and price < filters.min_price:
            return False
        if filters.max_price is not None and price > filters.max_price:
            return False
    elif filters.min_price is not None or filters.max_price is not None:
        return False
    if filters.min_area is not None and (listing.area is None or listing.area < filters.min_area):
        return False
    if filters.max_area is not None and (listing.area is None or listing.area > filters.max_area):
        return False
    if filters.min_floor is not None and (listing.floor is None or listing.floor < filters.min_floor):
        return False
    if filters.max_floor is not None and (listing.floor is None or listing.floor > filters.max_floor):
        return False

    haystack = f"{listing.title} {listing.description} {' '.join(listing.attributes.values())}".lower()
    required = {
        "furnished": ("мебел", "mobilat"),
        "washing_machine": ("стиральн", "mașină de spălat"),
        "refrigerator": ("холодильник", "frigider"),
        "air_conditioner": ("кондиционер", "aer condiționat"),
        "internet": ("интернет", "internet"),
    }
    for field_name, needles in required.items():
        wanted = getattr(filters, field_name)
        present = any(needle in haystack for needle in needles)
        if wanted is True and not present:
            return False
        if wanted is False and present:
            return False
    if filters.housing_stock and filters.housing_stock.lower() not in haystack:
        return False
    return True
