"""Development-only, low-volume retailer smoke check; never used by automated tests."""

import asyncio
import json

from app.config import get_settings
from app.sources.http import SafeHttpClient
from app.sources.registry import default_registry

LIVE_PATHS = {
    "Robu": "https://robu.in/product-category/raspberry-pi-5/",
    "ThinkRobotics": "https://thinkrobotics.com/products/raspberry-pi-5",
    "Zbotic": "https://zbotic.in/product/holybro-pixhawk-6x-icm-45686/",
    "Evelta": "https://evelta.com/raspberry-pi-5-with-2-4-8gb-ram/",
}


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
        for retailer, url in LIVE_PATHS.items():
            adapter = registry.resolve(url)
            try:
                html = await client.get_text(url)
                extraction = adapter.parse_product(html, url)
                discovered = adapter.discover_products(html, url, limit=5)
                print(
                    json.dumps(
                        {
                            "retailer": retailer,
                            "reachable": True,
                            "bytes": len(html.encode("utf-8")),
                            "status": extraction.status.value,
                            "name": extraction.product_name,
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
