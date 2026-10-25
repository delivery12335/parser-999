from __future__ import annotations

import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.api.server import create_api
from app.bot.handlers import router
from app.config import get_settings
from app.database.repository import Repository
from app.parser.parser import ListingParser
from app.services.calls import CallService
from app.services.images import ImageService
from app.services.listings import ListingsService
from app.services.monitoring import Monitor


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is empty; copy .env.example to .env and configure it")
    if len(settings.android_api_token) < 32:
        raise RuntimeError("ANDROID_API_TOKEN must contain at least 32 characters")

    repository = Repository(settings.database_url)
    await repository.init()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    parser = ListingParser(settings)
    image_service = ImageService(settings.request_timeout)
    listings_service = ListingsService(parser, repository)
    call_service = CallService(repository, settings)
    monitor = Monitor(bot, repository, listings_service, image_service, settings.check_interval)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    dispatcher["repository"] = repository
    dispatcher["listings_service"] = listings_service
    dispatcher["image_service"] = image_service
    dispatcher["call_service"] = call_service

    api = create_api(settings, repository)
    server = uvicorn.Server(uvicorn.Config(api, host=settings.server_host, port=settings.server_port, log_level=settings.log_level.lower()))
    tasks = [asyncio.create_task(server.serve()), asyncio.create_task(monitor.run())]
    try:
        await dispatcher.start_polling(bot)
    finally:
        monitor.stop()
        server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)
        await parser.close()
        await image_service.close()
        await repository.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
