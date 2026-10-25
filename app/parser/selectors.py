"""All site-specific selectors and labels live here for easy maintenance."""

BASE_URL = "https://999.md"

SEARCH_CARD_SELECTORS = (
    "article[data-id]",
    "li.ads-list-photo-item",
    "li.ads-list-item",
    "[class*='AdCard']",
)
SEARCH_LINK_SELECTORS = (
    "a[href*='/ru/']",
    "a[href*='/ro/']",
)

TITLE_SELECTORS = ("h1", "h2", "meta[property='og:title']", "[class*='styles_advert__title']", ".adPage__content__header")
PRICE_SELECTORS = ("[class*='styles_advert__price']", ".adPage__content__price-feature", "[itemprop='price']")
DESCRIPTION_SELECTORS = ("[itemprop='description']", "meta[property='og:description']", ".adPage__content__description", "[class*='description']")
IMAGE_SELECTORS = (
    "meta[property='og:image']",
    "img[id^='thumb-'][src*='simpalsmedia.com/999.md/BoardImages']",
    "img[alt$='.jpg'][src*='simpalsmedia.com/999.md/BoardImages']",
    "img[alt$='.jpeg'][src*='simpalsmedia.com/999.md/BoardImages']",
    "img[alt$='.png'][src*='simpalsmedia.com/999.md/BoardImages']",
    "img[alt$='.webp'][src*='simpalsmedia.com/999.md/BoardImages']",
)
ATTRIBUTE_ROW_SELECTORS = (".adPage__content__features__item", "[class*='feature']", "dl > div")
PHONE_SELECTORS = ("a[href^='tel:']", "[data-phone]", "[class*='phone']")
PUBLISHED_SELECTORS = ("time[datetime]", "[class*='date']")

DISTRICT_ALIASES = {
    "ботаник": "Ботаника",
    "botanica": "Ботаника",
    "центр": "Центр",
    "centru": "Центр",
    "рышкановка": "Рышкановка",
    "riscani": "Рышкановка",
    "rîșcani": "Рышкановка",
    "чеканы": "Чеканы",
    "чокана": "Чеканы",
    "ciocana": "Чеканы",
    "буюканы": "Буюканы",
    "buiucani": "Буюканы",
    "телецентр": "Телецентр",
    "telecentru": "Телецентр",
}

ATTRIBUTE_ALIASES = {
    "количество комнат": "rooms",
    "кол. комнат": "rooms",
    "numărul de camere": "rooms",
    "общая площадь": "area",
    "suprafața totală": "area",
    "этаж": "floor",
    "etaj": "floor",
    "количество этажей": "floors_total",
    "адрес": "address",
    "autorul anunțului": "seller_type",
    "автор объявления": "seller_type",
    "жилой фонд": "housing_stock",
}

# Public option IDs observed in the site's current filter form. Keeping them
# here isolates site changes from parser and Telegram business logic.
DISTRICT_OPTION_IDS = {
    "Ботаника": "15665",
    "Центр": "15664",
    "Рышкановка": "15667",
    "Чеканы": "15669",
    "Буюканы": "15666",
    "Телецентр": "15668",
}
ROOM_OPTION_IDS = {1: "893", 2: "894", 3: "902"}
SELLER_OPTION_IDS = {"owner": "18895", "agency": "18894", "developer": "20364"}
HOUSING_OPTION_IDS = {"secondary": "19109", "new": "19110"}
