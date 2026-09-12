"""Development-only, low-volume retailer smoke check; never used by automated tests."""

import asyncio
import json

from app.config import get_settings
from app.sources.http import SafeHttpClient
from app.sources.registry import default_registry

LIVE_PATHS = (
    ("Robu", "category", "https://robu.in/product-category/raspberry-pi-5/"),
    (
        "ThinkRobotics",
        "Raspberry Pi 5",
        "https://thinkrobotics.com/products/raspberry-pi-5",
    ),
    (
        "ThinkRobotics",
        "flight controller",
        "https://thinkrobotics.com/products/pixhawk-kit-online",
    ),
    (
        "ThinkRobotics",
        "flight-controller accessory",
        "https://thinkrobotics.com/products/apm-pixhawk-power-module-online",
    ),
    (
        "ThinkRobotics",
        "HAT/out of stock",
        "https://thinkrobotics.com/products/raspberry-pi-ai-hat",
    ),
    (
        "ThinkRobotics",
        "pre-order candidate",
        "https://thinkrobotics.com/products/official-raspberry-pi-5-csi-fpc-flexible-cable",
    ),
    (
        "Zbotic",
        "Pixhawk 6X",
        "https://zbotic.in/product/holybro-pixhawk-6x-icm-45686/",
    ),
    (
        "Evelta",
        "Raspberry Pi 5",
        "https://evelta.com/raspberry-pi-5-with-2-4-8gb-ram/",
    ),
)


async def run() -> int:
    settings = get_settings()
    registry = default_registry()
    client = SafeHttpClient(
        allowed_domains=registry.domains,
        timeout_seconds=settings.request_timeout,
        max_retries=0,
        user_agent=settings.user_agent,
    )
    failures = 0
    try:
        for retailer, sample, url in LIVE_PATHS:
            adapter = registry.resolve(url)
            try:
                html = await client.get_text(url)
                extraction = adapter.parse_product(html, url)
                discovered = adapter.discover_products(html, url, limit=5)
                print(
                    json.dumps(
                        {
                            "retailer": retailer,
                            "sample": sample,
                            "reachable": True,
                            "bytes": len(html.encode("utf-8")),
                            "status": extraction.status.value,
                            "name": extraction.product_name,
                            "price": str(extraction.price)
                            if extraction.price is not None
                            else None,
                            "currency": extraction.currency,
                            "manufacturer": extraction.manufacturer,
                            "category": extraction.category,
                            "variant_count": len(extraction.attributes.get("variants", [])),
                            "classification_source": extraction.classification_source,
                            "discovery_links": len(discovered),
                        }
                    )
                )
            except Exception as exc:
                failures += 1
                print(
                    json.dumps(
                        {
                            "retailer": retailer,
                            "sample": sample,
                            "reachable": False,
                            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                        }
                    )
                )
    finally:
        await client.close()
    return failures


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
