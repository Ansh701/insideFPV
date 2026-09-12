from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CategoryWatch, Product, Retailer, TelegramUser, WatchlistItem


@dataclass(frozen=True)
class SeedResult:
    retailers_created: int
    products_created: int
    category_watches_created: int
    watches_created: int


RETAILERS = (
    ("Robu", "robu.in"),
    ("ThinkRobotics", "thinkrobotics.com"),
    ("Zbotic", "zbotic.in"),
    ("Evelta", "evelta.com"),
)

PRODUCTS = (
    {
        "retailer": "ThinkRobotics",
        "external_identifier": "SBC1067",
        "canonical_url": "https://thinkrobotics.com/products/raspberry-pi-5",
        "name": "Raspberry Pi 5",
        "normalized_name": "raspberry pi 5",
        "manufacturer": "Raspberry Pi",
        "category": "Companion Computers",
    },
    {
        "retailer": "Zbotic",
        "external_identifier": "AI6681",
        "canonical_url": "https://zbotic.in/product/waveshare-pcie-to-ch-adapter-raspberry-pi-2280-2260-2242",
        "name": "Raspberry Pi 5-compatible HAT",
        "normalized_name": "raspberry pi 5 compatible hat",
        "manufacturer": "Waveshare",
        "category": "HATs & Carrier Boards",
    },
    {
        "retailer": "Zbotic",
        "external_identifier": "AI7874",
        "canonical_url": "https://zbotic.in/product/holybro-pixhawk-6x-icm-45686",
        "name": "Holybro Pixhawk 6X",
        "normalized_name": "holybro pixhawk 6x",
        "manufacturer": "Holybro",
        "category": "Flight Controllers",
    },
)

CATEGORY_URLS = {
    "Robu": {
        "Flight Controllers": "https://robu.in/product-category/flight-controller-accessories/",
        "Companion Computers": "https://robu.in/product-category/microcontroller-development-board/raspberry-pi-microcontroller-development-board/",
    },
    "ThinkRobotics": {
        "Flight Controllers": "https://thinkrobotics.com/collections/drone-controllers-online",
        "Companion Computers": "https://thinkrobotics.com/collections/raspberry-pi",
    },
    "Zbotic": {
        "Flight Controllers": "https://zbotic.in/product-category/drone-parts/flight-controller-amp-accessories/",
        "Companion Computers": "https://zbotic.in/product-category/development-boards/raspberry-pi/",
    },
    "Evelta": {
        "Flight Controllers": "https://evelta.com/drone-parts/",
        "Companion Computers": "https://evelta.com/development-boards-and-kits/raspberry-pi-and-accessories/",
    },
}


async def seed_database(session: AsyncSession) -> SeedResult:
    retailers_created = 0
    products_created = 0
    category_watches_created = 0
    watches_created = 0
    retailer_by_name = {item.name: item for item in (await session.scalars(select(Retailer))).all()}
    for name, domain in RETAILERS:
        if name not in retailer_by_name:
            retailer = Retailer(name=name, domain=domain)
            session.add(retailer)
            await session.flush()
            retailer_by_name[name] = retailer
            retailers_created += 1

    existing_urls = set((await session.scalars(select(Product.canonical_url))).all())
    for definition in PRODUCTS:
        if definition["canonical_url"] in existing_urls:
            continue
        session.add(
            Product(
                retailer_id=retailer_by_name[definition["retailer"]].id,
                external_identifier=definition["external_identifier"],
                canonical_url=definition["canonical_url"],
                name=definition["name"],
                normalized_name=definition["normalized_name"],
                manufacturer=definition["manufacturer"],
                category=definition["category"],
            )
        )
        products_created += 1

    existing_watches = {
        (item.retailer_id, item.category, item.query)
        for item in (await session.scalars(select(CategoryWatch))).all()
    }
    for retailer_name, categories in CATEGORY_URLS.items():
        retailer = retailer_by_name[retailer_name]
        for category, url in categories.items():
            key = (retailer.id, category, "")
            if key in existing_watches:
                continue
            session.add(
                CategoryWatch(
                    retailer_id=retailer.id,
                    category=category,
                    query="",
                    source_url=url,
                )
            )
            category_watches_created += 1

    user = await session.scalar(select(TelegramUser).where(TelegramUser.telegram_user_id == 0))
    if user is None:
        user = TelegramUser(
            telegram_user_id=0,
            chat_id=0,
            username="dashboard-demo",
            first_name="Dashboard",
        )
        session.add(user)
        await session.flush()
    product_urls = [definition["canonical_url"] for definition in PRODUCTS]
    tracked_products = list(
        (
            await session.scalars(select(Product).where(Product.canonical_url.in_(product_urls)))
        ).all()
    )
    existing_product_ids = set(
        (
            await session.scalars(
                select(WatchlistItem.product_id).where(
                    WatchlistItem.telegram_user_id == user.id,
                )
            )
        ).all()
    )
    for product in tracked_products:
        if product.id in existing_product_ids:
            continue
        session.add(WatchlistItem(telegram_user_id=user.id, product_id=product.id))
        watches_created += 1
    await session.commit()
    return SeedResult(
        retailers_created,
        products_created,
        category_watches_created,
        watches_created,
    )
