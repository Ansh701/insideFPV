from pathlib import Path

import pytest

from app.models import ProductStatus
from app.sources.evelta import EveltaAdapter
from app.sources.registry import default_registry
from app.sources.robu import RobuAdapter
from app.sources.thinkrobotics import ThinkRoboticsAdapter
from app.sources.zbotic import ZboticAdapter

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.parametrize(
    ("adapter", "fixture", "expected_status", "expected_price", "expected_name"),
    [
        (
            RobuAdapter(),
            "robu_in_stock.html",
            ProductStatus.IN_STOCK,
            "8199.00",
            "Raspberry Pi 5 Model 8GB",
        ),
        (
            ThinkRoboticsAdapter(),
            "thinkrobotics_out_of_stock.html",
            ProductStatus.OUT_OF_STOCK,
            "194.99",
            "CRIUS Pixhawk I2C Splitter",
        ),
        (
            ZboticAdapter(),
            "zbotic_preorder.html",
            ProductStatus.PREORDER,
            "48008.68",
            "Holybro Pixhawk 6X Standard Set",
        ),
        (
            EveltaAdapter(),
            "evelta_in_stock.html",
            ProductStatus.IN_STOCK,
            "4550.00",
            "Raspberry Pi 5 With 2/4/8GB RAM",
        ),
    ],
)
def test_adapter_parses_captured_storefront_evidence(
    adapter: object,
    fixture: str,
    expected_status: ProductStatus,
    expected_price: str,
    expected_name: str,
) -> None:
    html = (FIXTURES / fixture).read_text(encoding="utf-8")

    result = adapter.parse_product(html, f"https://{adapter.domain}/product/example")  # type: ignore[attr-defined]

    assert result.status is expected_status
    assert str(result.price) == expected_price
    assert result.product_name == expected_name
    assert result.currency == "INR"
    assert result.classification_source == "DETERMINISTIC"


def test_ambiguous_page_stays_unknown_instead_of_guessing() -> None:
    result = RobuAdapter().parse_product(
        "<html><body><h1>Flight Controller</h1><p>Contact us for details</p></body></html>",
        "https://robu.in/product/controller",
    )

    assert result.status is ProductStatus.UNKNOWN
    assert result.confidence < 0.8


def test_registry_resolves_all_supported_domains_without_business_logic_conditionals() -> None:
    registry = default_registry()

    assert registry.resolve("https://robu.in/product/a").name == "Robu"
    assert registry.resolve("https://thinkrobotics.com/products/a").name == "ThinkRobotics"
    assert registry.resolve("https://zbotic.in/product/a").name == "Zbotic"
    assert registry.resolve("https://evelta.com/a").name == "Evelta"
