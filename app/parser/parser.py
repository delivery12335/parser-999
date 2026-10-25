from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import Settings
from app.parser import selectors
from app.parser.filters import matches_filters
from app.parser.models import Listing, SearchFilters

logger = logging.getLogger(__name__)


class ParserBlockedError(RuntimeError):
    """Raised when the public page is protected and parsing must stop."""


class ListingParser:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=settings.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent, "Accept-Language": "ru,en;q=0.8"},
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _get(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.get(url)
                if response.status_code in {403, 429}:
                    raise ParserBlockedError(
                        f"999.md returned {response.status_code}; CAPTCHA/protection is not bypassed"
                    )
                response.raise_for_status()
                return response
            except ParserBlockedError:
                raise
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Failed to load {url}") from last_error

    async def search(self, filters: SearchFilters) -> list[Listing]:
        links: list[str] = []
        seen: set[str] = set()
        search_url = self._search_url(filters)
        for page in range(self.settings.parser_pages):
            separator = "&" if "?" in search_url else "?"
            response = await self._get(f"{search_url}{separator}page={page}")
            soup = BeautifulSoup(response.content.decode("utf-8", errors="replace"), "html.parser")
            self._raise_if_challenge(soup)
            for link in self._listing_links(soup):
                if link not in seen:
                    links.append(link)
                    seen.add(link)

        semaphore = asyncio.Semaphore(4)

        async def load(url: str) -> Listing | None:
            async with semaphore:
                try:
                    return await self.get_listing(url)
                except ParserBlockedError:
                    raise
                except Exception:
                    logger.exception("Could not parse listing %s", url)
                    return None

        results = await asyncio.gather(*(load(url) for url in links))
        return [listing for listing in results if listing and matches_filters(listing, filters)]

    def _search_url(self, filters: SearchFilters) -> str:
        parts = urlsplit(self.settings.search_url)
        managed_prefixes = ("o_30_241", "o_32_9", "o_9453_795", "o_2307_852")
        params = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if not key.startswith(managed_prefixes)]
        room_ids = [selectors.ROOM_OPTION_IDS[room] for room in sorted(filters.rooms) if room in selectors.ROOM_OPTION_IDS]
        district_ids = [selectors.DISTRICT_OPTION_IDS[name] for name in sorted(filters.districts) if name in selectors.DISTRICT_OPTION_IDS]
        seller_ids = [selectors.SELLER_OPTION_IDS[value.value] for value in sorted(filters.seller_types, key=str) if value.value in selectors.SELLER_OPTION_IDS]
        if room_ids:
            params.append(("o_30_241", ",".join(room_ids)))
        if district_ids:
            params.append(("o_32_9", ",".join(district_ids)))
        if seller_ids and "any" not in {value.value for value in filters.seller_types}:
            params.append(("o_9453_795", ",".join(seller_ids)))
        if filters.housing_stock in selectors.HOUSING_OPTION_IDS:
            params.append(("o_2307_852", selectors.HOUSING_OPTION_IDS[filters.housing_stock]))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params, doseq=True, safe=","), parts.fragment))

    async def get_listing(self, url: str) -> Listing:
        response = await self._get(urljoin(selectors.BASE_URL, url))
        soup = BeautifulSoup(response.content.decode("utf-8", errors="replace"), "html.parser")
        self._raise_if_challenge(soup)
        canonical = soup.select_one("link[rel='canonical']")
        final_url = canonical.get("href") if canonical and canonical.get("href") else str(response.url)
        structured = self._structured_product(soup)
        title = str(structured.get("name") or self._first_text(soup, selectors.TITLE_SELECTORS) or "Квартира")
        price, currency = self._parse_price(soup, structured)
        attributes = self._parse_attributes(soup)
        description = str(structured.get("description") or self._first_text(soup, selectors.DESCRIPTION_SELECTORS) or "") or None
        district = self._district_from_text(" ".join([title, description or "", *attributes.values()]))
        rooms = self._as_int(attributes.get("rooms")) or self._rooms_from_title(title)
        floor, floors_total = self._parse_floor(attributes)
        seller_type = self._seller_type(attributes, soup.get_text(" ", strip=True))
        external_id = self._external_id(final_url, soup, title, price, attributes.get("address"))
        return Listing(
            external_id=external_id,
            title=title,
            url=final_url,
            price=price,
            currency=currency,
            district=district,
            address=attributes.get("address"),
            rooms=rooms,
            area=self._as_float(attributes.get("area")),
            floor=floor,
            floors_total=floors_total,
            seller_type=seller_type,
            phone=self._phone(soup, description),
            description=description,
            image_urls=self._images(soup, structured),
            published_at=self._published(soup),
            attributes=attributes,
        )

    @staticmethod
    def _raise_if_challenge(soup: BeautifulSoup) -> None:
        text = soup.get_text(" ", strip=True).lower()
        if "captcha" in text or "cloudflare" in text or "проверка безопасности" in text:
            raise ParserBlockedError("Protection page detected; refusing to bypass it")

    @staticmethod
    def _listing_links(soup: BeautifulSoup) -> list[str]:
        cards: list[Tag] = []
        for selector in selectors.SEARCH_CARD_SELECTORS:
            cards.extend(soup.select(selector))
        roots = cards or [soup]
        links: list[str] = []
        for root in roots:
            for selector in selectors.SEARCH_LINK_SELECTORS:
                for anchor in root.select(selector):
                    href = anchor.get("href", "")
                    path = urlparse(href).path
                    if re.fullmatch(r"/(?:ru|ro)/\d{5,}", path):
                        links.append(urljoin(selectors.BASE_URL, href))
        return links

    @staticmethod
    def _first_text(soup: BeautifulSoup, candidates: tuple[str, ...]) -> str | None:
        for selector in candidates:
            node = soup.select_one(selector)
            if node:
                value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
                if value:
                    return re.sub(r"\s+", " ", str(value)).strip()
        return None

    @staticmethod
    def _structured_product(soup: BeautifulSoup) -> dict[str, object]:
        for script in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(script.string or "{}")
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for candidate in candidates:
                if isinstance(candidate, dict) and candidate.get("@type") in {"Product", "Apartment", "Offer"}:
                    return candidate
        return {}

    def _parse_price(self, soup: BeautifulSoup, structured: dict[str, object]) -> tuple[Decimal | None, str | None]:
        offers = structured.get("offers")
        if isinstance(offers, dict) and offers.get("price") is not None:
            try:
                return Decimal(str(offers["price"])), str(offers.get("priceCurrency") or "") or None
            except InvalidOperation:
                pass
        raw = self._first_text(soup, selectors.PRICE_SELECTORS) or ""
        meta = soup.select_one("[itemprop='price']")
        if meta and meta.get("content"):
            raw_price = str(meta.get("content")).strip().replace(" ", "").replace(",", ".")
            try:
                parsed_price = Decimal(raw_price)
                currency_text = raw.lower()
                currency = "EUR" if "€" in raw or "eur" in currency_text else "MDL" if "lei" in currency_text or "mdl" in currency_text else None
                return parsed_price, currency
            except InvalidOperation:
                pass
        currency = "EUR" if "€" in raw or "eur" in raw.lower() else "MDL" if "lei" in raw.lower() or "mdl" in raw.lower() else None
        match = re.search(r"\d[\d\s.,]*", raw)
        if not match:
            return None, currency
        normalized = match.group(0).replace(" ", "").replace(",", ".")
        try:
            return Decimal(normalized), currency
        except InvalidOperation:
            return None, currency

    @staticmethod
    def _parse_attributes(soup: BeautifulSoup) -> dict[str, str]:
        result: dict[str, str] = {}
        rows: list[Tag] = []
        for selector in selectors.ATTRIBUTE_ROW_SELECTORS:
            rows.extend(soup.select(selector))
        for row in rows:
            parts = [re.sub(r"\s+", " ", value).strip(" :") for value in row.stripped_strings]
            if len(parts) < 2:
                continue
            label, value = parts[0].lower(), " ".join(parts[1:])
            canonical = next((name for alias, name in selectors.ATTRIBUTE_ALIASES.items() if alias in label), None)
            result[canonical or label] = value
        feature_map = {
            "795": "seller_type",
            "241": "rooms",
            "852": "housing_stock",
            "248": "floor",
            "249": "floors_total",
        }
        for anchor in soup.select("a[href*='exo_']"):
            href = str(anchor.get("href", ""))
            match = re.search(r"exo_(\d+)=", href)
            if match and match.group(1) in feature_map:
                result[feature_map[match.group(1)]] = anchor.get_text(" ", strip=True)
        full_text = soup.get_text(" ", strip=True)
        area = re.search(r"Общая площадь\s+(\d+(?:[.,]\d+)?)\s*м", full_text, re.IGNORECASE)
        if area:
            result["area"] = area.group(1)
        address = re.search(
            r"((?:Кишин[её]в мун\.,\s*)?Кишин[её]в,\s*(?:Ботаника|Центр|Рышкановка|Чокана|Чеканы|Буюканы|Телецентр)[^|]{0,140}?)\s+Смотреть все квартиры",
            full_text,
            re.IGNORECASE,
        )
        if address:
            result["address"] = address.group(1).strip()
        return result

    @staticmethod
    def _images(soup: BeautifulSoup, structured: dict[str, object]) -> list[str]:
        found: list[str] = []
        def normalize(url: str) -> str:
            normalized = re.sub(r"/\d+x\d+/", "/900x900/", urljoin(selectors.BASE_URL, url))
            return re.sub(r"(BoardImages/900x900)/+", r"\1/", normalized)

        structured_images = structured.get("image", [])
        for url in ([structured_images] if isinstance(structured_images, str) else structured_images if isinstance(structured_images, list) else []):
            if isinstance(url, str):
                url = normalize(url)
                if url not in found:
                    found.append(url)
        for selector in selectors.IMAGE_SELECTORS:
            for node in soup.select(selector):
                url = node.get("content") or node.get("data-src") or node.get("src")
                if not url or "BoardImages" not in url:
                    continue
                url = normalize(str(url))
                if url not in found:
                    found.append(url)
        return found

    @staticmethod
    def _phone(soup: BeautifulSoup, description: str | None) -> str | None:
        candidates: list[str] = []
        if description:
            candidates.extend(re.findall(r"(?:\+?373[\s().-]*)?[67]\d(?:[\s().-]*\d){6}", description))
        for selector in selectors.PHONE_SELECTORS:
            for node in soup.select(selector):
                if node.find_parent("footer") or "support" in " ".join(node.get("class", [])).lower():
                    continue
                value = node.get("href", "").removeprefix("tel:") or node.get("data-phone", "") or node.get_text(" ", strip=True)
                candidates.append(value)
        for value in candidates:
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 8 and digits[-8] in "67":
                return "+373" + digits[-8:]
        return None

    @staticmethod
    def _published(soup: BeautifulSoup) -> datetime | None:
        for selector in selectors.PUBLISHED_SELECTORS:
            node = soup.select_one(selector)
            if not node:
                continue
            raw = node.get("datetime") or node.get_text(" ", strip=True)
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
        text = soup.get_text(" ", strip=True)
        match = re.search(r"(?:Обновлено|Опубликовано)\s*:\s*(\d{1,2})\s+([а-яё]+)\.?\s+(\d{4}),\s*(\d{1,2}):(\d{2})", text, re.IGNORECASE)
        months = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "мая": 5, "июн": 6, "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}
        if match:
            month = months.get(match.group(2)[:3].lower())
            if month:
                return datetime(int(match.group(3)), month, int(match.group(1)), int(match.group(4)), int(match.group(5)))
        return None

    @staticmethod
    def _district_from_text(text: str) -> str | None:
        lowered = text.lower()
        return next((canonical for alias, canonical in selectors.DISTRICT_ALIASES.items() if alias in lowered), None)

    @staticmethod
    def _rooms_from_title(title: str) -> int | None:
        match = re.search(r"(^|\D)([1-5])\s*[-–]?\s*(?:ком|cam)", title.lower())
        return int(match.group(2)) if match else None

    @staticmethod
    def _as_int(value: str | None) -> int | None:
        match = re.search(r"\d+", value or "")
        return int(match.group()) if match else None

    @staticmethod
    def _as_float(value: str | None) -> float | None:
        match = re.search(r"\d+(?:[.,]\d+)?", value or "")
        return float(match.group().replace(",", ".")) if match else None

    def _parse_floor(self, attributes: dict[str, str]) -> tuple[int | None, int | None]:
        raw = attributes.get("floor", "")
        values = [int(value) for value in re.findall(r"\d+", raw)]
        floor = values[0] if values else None
        total = values[1] if len(values) > 1 else self._as_int(attributes.get("floors_total"))
        return floor, total

    @staticmethod
    def _seller_type(attributes: dict[str, str], full_text: str) -> str | None:
        value = f"{attributes.get('seller_type', '')} {full_text}".lower()
        if "агентств" in value or "agenție" in value:
            return "agency"
        if "застройщик" in value or "dezvoltator" in value:
            return "developer"
        if "частное лицо" in value or "persoană fizică" in value or "собственник" in value:
            return "owner"
        return None

    @staticmethod
    def _external_id(url: str, soup: BeautifulSoup, title: str, price: Decimal | None, address: str | None) -> str:
        match = re.search(r"/(\d{5,})(?:\D|$)", url)
        data_id = soup.select_one("[data-id]")
        if match:
            return match.group(1)
        if data_id and data_id.get("data-id"):
            return str(data_id.get("data-id"))
        return hashlib.sha256(f"{url}|{price}|{address}|{title}".encode()).hexdigest()
