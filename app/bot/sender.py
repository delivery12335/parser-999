from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputMediaPhoto

from app.bot.keyboards.common import listing_keyboard
from app.bot.presentation import listing_caption
from app.database.models import Listing
from app.services.images import ImageService

logger = logging.getLogger(__name__)


async def send_listing(bot: Bot, chat_id: int, listing: Listing, images: ImageService, *, fresh: bool = False) -> None:
    caption = listing_caption(listing, fresh=fresh)
    if not listing.main_image_url:
        await bot.send_message(chat_id, caption, reply_markup=listing_keyboard(listing))
        return
    try:
        await bot.send_photo(chat_id, listing.main_image_url, caption=caption, reply_markup=listing_keyboard(listing))
    except TelegramBadRequest:
        logger.info("Telegram could not fetch image; using temporary download for %s", listing.id)
        async with images.downloaded(listing.main_image_url) as path:
            await bot.send_photo(chat_id, FSInputFile(path), caption=caption, reply_markup=listing_keyboard(listing))


async def send_remaining_photos(bot: Bot, chat_id: int, listing: Listing, images: ImageService) -> None:
    urls = [item.image_url for item in listing.images[1:]]
    if not urls:
        await bot.send_message(chat_id, "Других фотографий нет.")
        return
    for start in range(0, len(urls), 10):
        chunk = urls[start:start + 10]
        try:
            await bot.send_media_group(chat_id, [InputMediaPhoto(media=url) for url in chunk])
        except TelegramBadRequest:
            paths: list[str] = []
            contexts = []
            try:
                for url in chunk:
                    context = images.downloaded(url)
                    contexts.append(context)
                    paths.append(await context.__aenter__())
                await bot.send_media_group(chat_id, [InputMediaPhoto(media=FSInputFile(path)) for path in paths])
            finally:
                for context in reversed(contexts):
                    await context.__aexit__(None, None, None)
