from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.common import extra_filters_keyboard, filters_keyboard, main_keyboard
from app.bot.sender import send_listing, send_remaining_photos
from app.bot.states import FilterStates
from app.config import Settings
from app.database.repository import Repository
from app.parser.parser import ParserBlockedError
from app.services.calls import CallService
from app.services.images import ImageService
from app.services.listings import ListingsService

logger = logging.getLogger(__name__)
router = Router()


async def _edit(callback: CallbackQuery, text: str, **kwargs: object) -> None:
    if callback.message:
        await callback.message.edit_text(text, **kwargs)
    await callback.answer()


@router.message(CommandStart())
async def start(message: Message, repository: Repository) -> None:
    await repository.get_or_create_user(message.from_user.id)
    owner_note = "\n\n👑 Вы владелец бота: только вам доступна отправка команд звонка." if await repository.is_owner(message.from_user.id) else ""
    await message.answer(
        "Я найду новые квартиры на 999.md по вашим фильтрам." + owner_note,
        reply_markup=main_keyboard(),
    )


@router.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery) -> None:
    await _edit(callback, "Главное меню", reply_markup=main_keyboard())


@router.callback_query(F.data == "filters")
async def filters(callback: CallbackQuery, repository: Repository) -> None:
    _, record = await repository.get_filter(callback.from_user.id)
    await _edit(callback, "Настройте фильтры. Пустые группы автоматически возвращаются к значениям по умолчанию.", reply_markup=filters_keyboard(record))


@router.callback_query(F.data.startswith("flt:d:"))
async def toggle_district(callback: CallbackQuery, repository: Repository) -> None:
    record = await repository.toggle_filter_value(callback.from_user.id, "districts", callback.data.split(":", 2)[2])
    await callback.message.edit_reply_markup(reply_markup=filters_keyboard(record))
    await callback.answer()


@router.callback_query(F.data.startswith("flt:r:"))
async def toggle_room(callback: CallbackQuery, repository: Repository) -> None:
    record = await repository.toggle_filter_value(callback.from_user.id, "rooms", callback.data.rsplit(":", 1)[1])
    await callback.message.edit_reply_markup(reply_markup=filters_keyboard(record))
    await callback.answer()


@router.callback_query(F.data.startswith("flt:s:"))
async def toggle_seller(callback: CallbackQuery, repository: Repository) -> None:
    value = callback.data.rsplit(":", 1)[1]
    _, current = await repository.get_filter(callback.from_user.id)
    if value == "any":
        record = await repository.update_filter(callback.from_user.id, seller_types='["any"]')
    else:
        if "any" in current.seller_types:
            await repository.update_filter(callback.from_user.id, seller_types="[]")
        record = await repository.toggle_filter_value(callback.from_user.id, "seller_types", value)
    await callback.message.edit_reply_markup(reply_markup=filters_keyboard(record))
    await callback.answer()


@router.callback_query(F.data == "flt:currency")
async def currency(callback: CallbackQuery, repository: Repository) -> None:
    _, current = await repository.get_filter(callback.from_user.id)
    record = await repository.update_filter(callback.from_user.id, currency="MDL" if current.currency == "EUR" else "EUR")
    await callback.message.edit_reply_markup(reply_markup=filters_keyboard(record))
    await callback.answer()


@router.callback_query(F.data.in_({"flt:min", "flt:max"}))
async def ask_price(callback: CallbackQuery, state: FSMContext) -> None:
    is_max = callback.data == "flt:max"
    await state.set_state(FilterStates.waiting_max_price if is_max else FilterStates.waiting_min_price)
    await callback.message.answer(f"Введите {'максимальную' if is_max else 'минимальную'} цену числом или 0, чтобы сбросить:")
    await callback.answer()


@router.message(FilterStates.waiting_min_price)
@router.message(FilterStates.waiting_max_price)
async def save_price(message: Message, state: FSMContext, repository: Repository) -> None:
    try:
        value = Decimal((message.text or "").replace(",", "."))
        if value < 0:
            raise InvalidOperation
    except InvalidOperation:
        await message.answer("Нужно неотрицательное число. Попробуйте ещё раз.")
        return
    current = await state.get_state()
    field = "max_price" if current == FilterStates.waiting_max_price.state else "min_price"
    record = await repository.update_filter(message.from_user.id, **{field: None if value == 0 else value})
    await state.clear()
    await message.answer("Цена сохранена.", reply_markup=filters_keyboard(record))


@router.callback_query(F.data == "flt:extra")
async def extras(callback: CallbackQuery, repository: Repository) -> None:
    _, record = await repository.get_filter(callback.from_user.id)
    await _edit(callback, "Дополнительные фильтры: ➖ не учитывать, ✅ обязательно, ❌ исключить.", reply_markup=extra_filters_keyboard(record))


@router.callback_query(F.data.startswith("flt:b:"))
async def toggle_boolean(callback: CallbackQuery, repository: Repository) -> None:
    field = callback.data.rsplit(":", 1)[1]
    _, record = await repository.get_filter(callback.from_user.id)
    current = getattr(record, field)
    next_value = True if current is None else False if current is True else None
    record = await repository.update_filter(callback.from_user.id, **{field: next_value})
    await callback.message.edit_reply_markup(reply_markup=extra_filters_keyboard(record))
    await callback.answer()


@router.callback_query(F.data.startswith("flt:h:"))
async def housing_stock(callback: CallbackQuery, repository: Repository) -> None:
    value = callback.data.rsplit(":", 1)[1]
    _, current = await repository.get_filter(callback.from_user.id)
    record = await repository.update_filter(callback.from_user.id, housing_stock=None if current.housing_stock == value else value)
    await callback.message.edit_reply_markup(reply_markup=extra_filters_keyboard(record))
    await callback.answer("Сохранено")


@router.callback_query(F.data.in_({"flt:area", "flt:floor"}))
async def ask_extra_range(callback: CallbackQuery, state: FSMContext) -> None:
    is_area = callback.data == "flt:area"
    await state.set_state(FilterStates.waiting_area if is_area else FilterStates.waiting_floor)
    unit = "м²" if is_area else ""
    await callback.message.answer(
        f"Введите диапазон {'площади' if is_area else 'этажа'}: <code>от-до</code> {unit}. "
        "Можно оставить границу пустой (<code>-60</code> или <code>3-</code>), <code>0</code> сбрасывает фильтр."
    )
    await callback.answer()


@router.message(FilterStates.waiting_area)
@router.message(FilterStates.waiting_floor)
async def save_extra_range(message: Message, state: FSMContext, repository: Repository) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    current = await state.get_state()
    is_area = current == FilterStates.waiting_area.state
    prefix = "area" if is_area else "floor"
    if raw == "0":
        record = await repository.update_filter(message.from_user.id, **{f"min_{prefix}": None, f"max_{prefix}": None})
    else:
        try:
            left, right = raw.split("-", 1)
            converter = float if is_area else int
            minimum = converter(left) if left else None
            maximum = converter(right) if right else None
            if (minimum is not None and minimum < 0) or (maximum is not None and maximum < 0):
                raise ValueError
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError
        except (ValueError, TypeError):
            await message.answer("Формат не распознан. Пример: <code>35-70</code>, <code>-60</code>, <code>3-</code> или <code>0</code>.")
            return
        record = await repository.update_filter(
            message.from_user.id,
            **{f"min_{prefix}": minimum, f"max_{prefix}": maximum},
        )
    await state.clear()
    await message.answer("Дополнительный фильтр сохранён.", reply_markup=extra_filters_keyboard(record))


@router.callback_query(F.data == "search")
async def search(callback: CallbackQuery, bot: Bot, repository: Repository, listings_service: ListingsService, image_service: ImageService) -> None:
    await callback.answer("Ищу, это может занять несколько секунд…")
    user, record = await repository.get_filter(callback.from_user.id)
    try:
        listings = await listings_service.search(record)
    except ParserBlockedError:
        await callback.message.answer("999.md запросил проверку безопасности. Я не обхожу её; попробуйте позже или обновите SEARCH_URL.")
        return
    if not listings:
        await callback.message.answer("По текущим фильтрам ничего не найдено.", reply_markup=main_keyboard())
        return
    sent = 0
    for listing in listings[:20]:
        if not await repository.unseen(user.id, listing.id):
            continue
        await send_listing(bot, callback.from_user.id, listing, image_service)
        await repository.mark_sent(user.id, listing.id)
        sent += 1
    if not sent:
        await callback.message.answer("Новых объявлений нет — найденные уже были показаны.", reply_markup=main_keyboard())


@router.callback_query(F.data == "monitor")
async def monitor(callback: CallbackQuery, repository: Repository) -> None:
    _, current = await repository.get_filter(callback.from_user.id)
    record = await repository.update_filter(callback.from_user.id, monitoring_enabled=not current.monitoring_enabled)
    state = "включён" if record.monitoring_enabled else "выключен"
    await _edit(callback, f"🔔 Мониторинг {state}.", reply_markup=main_keyboard())


@router.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery, repository: Repository) -> None:
    _, record = await repository.get_filter(callback.from_user.id)
    text = (
        "📋 <b>Мои настройки</b>\n\n"
        f"Районы: {', '.join(__import__('json').loads(record.districts))}\n"
        f"Комнаты: {', '.join(map(str, __import__('json').loads(record.rooms)))}\n"
        f"Цена: {record.min_price or '—'} — {record.max_price or '—'} {record.currency}\n"
        f"Мониторинг: {'включён' if record.monitoring_enabled else 'выключен'}"
    )
    await _edit(callback, text, reply_markup=main_keyboard())


@router.callback_query(F.data == "favorites")
async def favorites(callback: CallbackQuery, bot: Bot, repository: Repository, image_service: ImageService) -> None:
    user, _ = await repository.get_filter(callback.from_user.id)
    items = await repository.favorites(user.id)
    await callback.answer()
    if not items:
        await callback.message.answer("Избранное пока пусто.", reply_markup=main_keyboard())
        return
    for listing in items:
        await send_listing(bot, callback.from_user.id, listing, image_service)


@router.callback_query(F.data.startswith("fav:"))
async def favorite(callback: CallbackQuery, repository: Repository) -> None:
    user, _ = await repository.get_filter(callback.from_user.id)
    await repository.add_favorite(user.id, int(callback.data.split(":")[1]))
    await callback.answer("Добавлено в избранное ❤️")


@router.callback_query(F.data.startswith("skip:"))
async def skip(callback: CallbackQuery) -> None:
    if callback.message:
        try:
            await callback.message.delete()
        except TelegramAPIError:
            await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("photos:"))
async def photos(callback: CallbackQuery, bot: Bot, repository: Repository, image_service: ImageService) -> None:
    listing = await repository.listing(int(callback.data.split(":")[1]))
    await callback.answer()
    if listing:
        await send_remaining_photos(bot, callback.from_user.id, listing, image_service)


@router.callback_query(F.data.startswith("call:"))
async def call(callback: CallbackQuery, bot: Bot, call_service: CallService) -> None:
    try:
        listing_id = int(callback.data.split(":")[1])
        if call_service.mode == "iphone":
            listing, _ = await call_service.present_on_iphone(callback.from_user.id, listing_id)
            await bot.send_contact(
                chat_id=callback.from_user.id,
                phone_number=listing.phone or "",
                first_name="Владелец квартиры",
            )
            await callback.message.answer(
                "Нажмите на номер в карточке контакта и подтвердите обычный звонок через iPhone."
            )
            command = None
        else:
            command = await call_service.request(callback.from_user.id, listing_id)
    except PermissionError:
        await callback.answer("Звонки разрешены только владельцу бота.", show_alert=True)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
    else:
        if command:
            await callback.answer(f"Команда {command.request_id[:8]} отправлена на Android.", show_alert=True)
        else:
            await callback.answer("Номер отправлен отдельной карточкой.")
