from __future__ import annotations

import json

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Filter, Listing


def main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Найти квартиры", callback_data="search")
    builder.button(text="⚙️ Фильтры", callback_data="filters")
    builder.button(text="🔔 Мониторинг", callback_data="monitor")
    builder.button(text="❤️ Избранное", callback_data="favorites")
    builder.button(text="📋 Мои настройки", callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()


def _selected(flag: bool, label: str) -> str:
    return f"✅ {label}" if flag else label


def filters_keyboard(record: Filter) -> InlineKeyboardMarkup:
    districts = set(json.loads(record.districts))
    rooms = {int(value) for value in json.loads(record.rooms)}
    sellers = set(json.loads(record.seller_types))
    builder = InlineKeyboardBuilder()
    for district in ("Ботаника", "Центр", "Рышкановка", "Чеканы", "Буюканы", "Телецентр"):
        builder.button(text=_selected(district in districts, district), callback_data=f"flt:d:{district}")
    for room in (1, 2, 3):
        builder.button(text=_selected(room in rooms, str(room)), callback_data=f"flt:r:{room}")
    for value, label in (("owner", "Собственник"), ("agency", "Агентство"), ("developer", "Застройщик"), ("any", "Любой")):
        builder.button(text=_selected(value in sellers, label), callback_data=f"flt:s:{value}")
    builder.button(text=f"💶 Валюта: {record.currency}", callback_data="flt:currency")
    builder.button(text=f"Цена от: {record.min_price or '—'}", callback_data="flt:min")
    builder.button(text=f"Цена до: {record.max_price or '—'}", callback_data="flt:max")
    builder.button(text="➕ Дополнительные", callback_data="flt:extra")
    builder.button(text="✅ Сохранить фильтры", callback_data="menu")
    builder.adjust(2, 2, 2, 3, 2, 2, 1, 1)
    return builder.as_markup()


def extra_filters_keyboard(record: Filter) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    values = (
        ("furnished", "Мебель", record.furnished),
        ("washing_machine", "Стиральная машина", record.washing_machine),
        ("refrigerator", "Холодильник", record.refrigerator),
        ("air_conditioner", "Кондиционер", record.air_conditioner),
        ("internet", "Интернет", record.internet),
    )
    for field, label, value in values:
        prefix = "✅" if value is True else "❌" if value is False else "➖"
        builder.button(text=f"{prefix} {label}", callback_data=f"flt:b:{field}")
    builder.button(text="🏗 Новострой", callback_data="flt:h:new")
    builder.button(text="🏠 Вторичный", callback_data="flt:h:secondary")
    builder.button(text="📐 Площадь", callback_data="flt:area")
    builder.button(text="🏢 Этаж", callback_data="flt:floor")
    builder.button(text="⬅️ Назад", callback_data="filters")
    builder.adjust(1)
    return builder.as_markup()


def listing_keyboard(listing: Listing) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if listing.phone:
        rows.append([InlineKeyboardButton(text="📞 Позвонить", callback_data=f"call:{listing.id}")])
    if len(listing.images) > 1:
        rows.append([InlineKeyboardButton(text="🖼 Все фото", callback_data=f"photos:{listing.id}")])
    rows.append([InlineKeyboardButton(text="🔗 Открыть 999.md", url=listing.url)])
    rows.append([
        InlineKeyboardButton(text="❤️ В избранное", callback_data=f"fav:{listing.id}"),
        InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip:{listing.id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
