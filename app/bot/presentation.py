from __future__ import annotations

import html

from app.database.models import Listing


def listing_caption(listing: Listing, *, fresh: bool = False) -> str:
    seller = {"owner": "Собственник", "agency": "Агентство", "developer": "Застройщик"}.get(listing.seller_type, "Не указан")
    parts = ["🔥 <b>Новая квартира</b>" if fresh else "🏠 <b>Квартира</b>", ""]
    parts.append(f"🏠 {html.escape(listing.title)}")
    if listing.district or listing.address:
        parts.append(f"📍 {html.escape(', '.join(filter(None, [listing.district, listing.address])))}")
    if listing.price is not None:
        symbol = "€" if listing.currency == "EUR" else "MDL"
        parts.append(f"💰 {listing.price:g} {symbol} / месяц")
    if listing.rooms:
        parts.append(f"🚪 {listing.rooms} комн.")
    if listing.area:
        parts.append(f"📐 {listing.area:g} м²")
    if listing.floor:
        parts.append(f"🏢 {listing.floor} этаж" + (f" из {listing.floors_total}" if listing.floors_total else ""))
    parts.append(f"👤 {seller}")
    if listing.phone:
        parts.append(f"📞 {html.escape(listing.phone)}")
    if listing.description:
        short = listing.description[:500] + ("…" if len(listing.description) > 500 else "")
        parts.extend(["", html.escape(short)])
    if listing.published_at:
        parts.extend(["", f"🕐 Опубликовано: {listing.published_at:%d.%m.%Y %H:%M}"])
    return "\n".join(parts)[:1024]
