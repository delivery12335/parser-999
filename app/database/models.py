from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class BotSetting(Base):
    __tablename__ = "bot_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    filters: Mapped["Filter"] = relationship(back_populates="user", cascade="all, delete-orphan")


class Filter(Base):
    __tablename__ = "filters"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    districts: Mapped[str] = mapped_column(Text, default='["Ботаника"]')
    rooms: Mapped[str] = mapped_column(Text, default="[1, 2]")
    seller_types: Mapped[str] = mapped_column(Text, default='["owner"]')
    min_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    max_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    min_area: Mapped[float | None] = mapped_column(Float)
    max_area: Mapped[float | None] = mapped_column(Float)
    min_floor: Mapped[int | None] = mapped_column(Integer)
    max_floor: Mapped[int | None] = mapped_column(Integer)
    furnished: Mapped[bool | None] = mapped_column(Boolean)
    washing_machine: Mapped[bool | None] = mapped_column(Boolean)
    refrigerator: Mapped[bool | None] = mapped_column(Boolean)
    air_conditioner: Mapped[bool | None] = mapped_column(Boolean)
    internet: Mapped[bool | None] = mapped_column(Boolean)
    housing_stock: Mapped[str | None] = mapped_column(String(30))
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped[User] = relationship(back_populates="filters")


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    district: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    rooms: Mapped[int | None] = mapped_column(Integer)
    area: Mapped[float | None] = mapped_column(Float)
    floor: Mapped[int | None] = mapped_column(Integer)
    floors_total: Mapped[int | None] = mapped_column(Integer)
    seller_type: Mapped[str | None] = mapped_column(String(30))
    phone: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    main_image_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    images: Mapped[list["ListingImage"]] = relationship(back_populates="listing", cascade="all, delete-orphan", order_by="ListingImage.position")


class ListingImage(Base):
    __tablename__ = "listing_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    image_url: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    listing: Mapped[Listing] = relationship(back_populates="images")
    __table_args__ = (UniqueConstraint("listing_id", "position"),)


class SentListing(Base):
    __tablename__ = "sent_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "listing_id"),)


class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "listing_id"),)


class Call(Base):
    __tablename__ = "calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str] = mapped_column(String(30))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_message: Mapped[str | None] = mapped_column(Text)
