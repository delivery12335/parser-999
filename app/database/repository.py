from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database.models import Base, BotSetting, Call, Favorite, Filter, Listing, ListingImage, SentListing, User, utcnow
from app.parser.models import Currency, Listing as ParsedListing, SearchFilters, SellerType


class Repository:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def get_or_create_user(self, telegram_id: int) -> User:
        async with self.sessions.begin() as session:
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                user = User(telegram_id=telegram_id)
                session.add(user)
                await session.flush()
                session.add(Filter(user_id=user.id))
            await session.execute(
                sqlite_insert(BotSetting)
                .values(key="owner_telegram_id", value=str(telegram_id))
                .on_conflict_do_nothing(index_elements=["key"])
            )
            return user

    async def owner_telegram_id(self) -> int | None:
        async with self.sessions() as session:
            value = await session.scalar(select(BotSetting.value).where(BotSetting.key == "owner_telegram_id"))
            return int(value) if value else None

    async def is_owner(self, telegram_id: int) -> bool:
        await self.get_or_create_user(telegram_id)
        return await self.owner_telegram_id() == telegram_id

    async def get_filter(self, telegram_id: int) -> tuple[User, Filter]:
        await self.get_or_create_user(telegram_id)
        async with self.sessions() as session:
            row = await session.execute(
                select(User, Filter).join(Filter).where(User.telegram_id == telegram_id)
            )
            return row.one()

    @staticmethod
    def to_search_filter(record: Filter) -> SearchFilters:
        return SearchFilters(
            districts=set(json.loads(record.districts)),
            rooms={int(v) for v in json.loads(record.rooms)},
            seller_types={SellerType(v) for v in json.loads(record.seller_types)},
            min_price=Decimal(str(record.min_price)) if record.min_price is not None else None,
            max_price=Decimal(str(record.max_price)) if record.max_price is not None else None,
            currency=Currency(record.currency),
            min_area=record.min_area,
            max_area=record.max_area,
            min_floor=record.min_floor,
            max_floor=record.max_floor,
            furnished=record.furnished,
            washing_machine=record.washing_machine,
            refrigerator=record.refrigerator,
            air_conditioner=record.air_conditioner,
            internet=record.internet,
            housing_stock=record.housing_stock,
        )

    async def toggle_filter_value(self, telegram_id: int, field: str, value: str) -> Filter:
        if field not in {"districts", "rooms", "seller_types"}:
            raise ValueError("Unsupported filter")
        _, record = await self.get_filter(telegram_id)
        values = json.loads(getattr(record, field))
        cast_value: int | str = int(value) if field == "rooms" else value
        if cast_value in values:
            values.remove(cast_value)
        else:
            values.append(cast_value)
        if not values:
            values = [1, 2] if field == "rooms" else (["Ботаника"] if field == "districts" else ["owner"])
        async with self.sessions.begin() as session:
            await session.execute(update(Filter).where(Filter.id == record.id).values({field: json.dumps(values, ensure_ascii=False)}))
        return (await self.get_filter(telegram_id))[1]

    async def update_filter(self, telegram_id: int, **values: object) -> Filter:
        _, record = await self.get_filter(telegram_id)
        allowed = {column.name for column in Filter.__table__.columns} - {"id", "user_id"}
        clean = {key: value for key, value in values.items() if key in allowed}
        async with self.sessions.begin() as session:
            await session.execute(update(Filter).where(Filter.id == record.id).values(**clean))
        return (await self.get_filter(telegram_id))[1]

    async def monitoring_users(self) -> list[tuple[User, Filter]]:
        async with self.sessions() as session:
            rows = await session.execute(select(User, Filter).join(Filter).where(Filter.monitoring_enabled.is_(True)))
            return list(rows.all())

    async def upsert_listing(self, parsed: ParsedListing) -> Listing:
        async with self.sessions.begin() as session:
            listing = await session.scalar(
                select(Listing).options(selectinload(Listing.images)).where(Listing.external_id == parsed.external_id)
            )
            values = dict(
                title=parsed.title, price=parsed.price, currency=parsed.currency, district=parsed.district,
                address=parsed.address, rooms=parsed.rooms, area=parsed.area, floor=parsed.floor,
                floors_total=parsed.floors_total, seller_type=parsed.seller_type, phone=parsed.phone,
                description=parsed.description, url=parsed.url, main_image_url=parsed.main_image_url,
                published_at=parsed.published_at,
            )
            if listing is None:
                listing = Listing(external_id=parsed.external_id, **values)
                session.add(listing)
                await session.flush()
            else:
                for key, value in values.items():
                    setattr(listing, key, value)
                await session.execute(delete(ListingImage).where(ListingImage.listing_id == listing.id))
            session.add_all(
                ListingImage(listing_id=listing.id, image_url=image_url, position=index)
                for index, image_url in enumerate(parsed.image_urls)
            )
            await session.flush()
            loaded = await session.scalar(
                select(Listing).options(selectinload(Listing.images))
                .where(Listing.id == listing.id).execution_options(populate_existing=True)
            )
            assert loaded is not None
            return loaded

    async def listing(self, listing_id: int) -> Listing | None:
        async with self.sessions() as session:
            return await session.scalar(select(Listing).options(selectinload(Listing.images)).where(Listing.id == listing_id))

    async def unseen(self, user_id: int, listing_id: int) -> bool:
        async with self.sessions() as session:
            return not bool(await session.scalar(select(SentListing.id).where(SentListing.user_id == user_id, SentListing.listing_id == listing_id)))

    async def mark_sent(self, user_id: int, listing_id: int) -> None:
        async with self.sessions.begin() as session:
            exists = await session.scalar(
                select(SentListing.id).where(SentListing.user_id == user_id, SentListing.listing_id == listing_id)
            )
            if not exists:
                session.add(SentListing(user_id=user_id, listing_id=listing_id))

    async def add_favorite(self, user_id: int, listing_id: int) -> None:
        async with self.sessions.begin() as session:
            exists = await session.scalar(
                select(Favorite.id).where(Favorite.user_id == user_id, Favorite.listing_id == listing_id)
            )
            if not exists:
                session.add(Favorite(user_id=user_id, listing_id=listing_id))

    async def favorites(self, user_id: int) -> list[Listing]:
        async with self.sessions() as session:
            result = await session.scalars(
                select(Listing).join(Favorite).options(selectinload(Listing.images))
                .where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc()).limit(30)
            )
            return list(result.unique())

    async def create_call(self, user_id: int, listing_id: int, phone: str, *, status: str = "pending") -> Call:
        async with self.sessions.begin() as session:
            if status == "pending":
                existing = await session.scalar(
                    select(Call).where(
                        Call.user_id == user_id,
                        Call.listing_id == listing_id,
                        Call.status.in_(["pending", "claimed", "dialing"]),
                    ).order_by(Call.requested_at.desc()).limit(1)
                )
                if existing:
                    return existing
            call = Call(request_id=str(uuid.uuid4()), user_id=user_id, listing_id=listing_id, phone=phone, status=status)
            session.add(call)
            await session.flush()
        return call

    async def claim_next_call(self) -> Call | None:
        async with self.sessions.begin() as session:
            call = await session.scalar(select(Call).where(Call.status == "pending").order_by(Call.requested_at).limit(1))
            if call is None:
                return None
            result = await session.execute(
                update(Call).where(Call.id == call.id, Call.status == "pending")
                .values(status="claimed", claimed_at=utcnow())
            )
            if result.rowcount != 1:
                return None
            call.status = "claimed"
            return call

    async def update_call_status(self, request_id: str, status: str, message: str | None = None) -> bool:
        allowed = {"dialing", "completed", "failed", "rejected"}
        if status not in allowed:
            raise ValueError("Invalid call status")
        async with self.sessions.begin() as session:
            result = await session.execute(
                update(Call).where(Call.request_id == request_id, Call.status.in_(["claimed", "dialing"]))
                .values(status=status, status_message=message, completed_at=utcnow() if status in {"completed", "failed", "rejected"} else None)
            )
            return result.rowcount == 1
