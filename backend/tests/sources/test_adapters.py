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


def test_thinkrobotics_parses_default_variant_selling_price_and_preserves_variants() -> None:
    html = (FIXTURES / "thinkrobotics_variants.html").read_text(encoding="utf-8")

    result = ThinkRoboticsAdapter().parse_product(
        html, "https://thinkrobotics.com/products/raspberry-pi-5"
    )

    assert result.status is ProductStatus.IN_STOCK
    assert str(result.price) == "7799.99"
    assert result.product_name == "Raspberry Pi 5"
    assert result.manufacturer == "Raspberry Pi"
    assert result.category == "Companion Computers"
    assert result.attributes["selected_variant"] == "2GB"
    assert result.attributes["compare_at_price"] == "7999.99"
    variants = result.attributes["variants"]
    assert isinstance(variants, list)
    assert variants[0] == {
        "name": "2GB",
        "available": True,
        "price": "7799.99",
        "compare_at_price": "7999.99",
        "sku": "SBC1067-2",
    }
    assert "compare_at_price" not in variants[1]


@pytest.mark.parametrize(
    ("price_markup", "availability_markup", "expected_status", "expected_price"),
    [
        ("₹ 15,999.50", "Add to cart", ProductStatus.IN_STOCK, "15999.50"),
        ("₹ 12,499.00", "Sold out", ProductStatus.OUT_OF_STOCK, "12499.00"),
        ("₹ 25,000.00", "Pre-order now", ProductStatus.PREORDER, "25000.00"),
        ("price unavailable", "Sold out", ProductStatus.OUT_OF_STOCK, None),
    ],
)
def test_thinkrobotics_deterministic_page_price_states(
    price_markup: str,
    availability_markup: str,
    expected_status: ProductStatus,
    expected_price: str | None,
) -> None:
    result = ThinkRoboticsAdapter().parse_product(
        f"<main><h1>Pixhawk Pro 6C</h1><span class='price'>{price_markup}</span>"
        f"<button>{availability_markup}</button></main>",
        "https://thinkrobotics.com/products/pixhawk-pro-6c",
    )

    actual_price = str(result.price) if result.price is not None else None
    assert result.status is expected_status
    assert actual_price == expected_price
    assert result.product_name == "Pixhawk Pro 6C"
    assert result.category == "Flight Controllers"


def test_thinkrobotics_ignores_retailer_name_as_manufacturer() -> None:
    html = (FIXTURES / "thinkrobotics_out_of_stock.html").read_text(encoding="utf-8")

    result = ThinkRoboticsAdapter().parse_product(
        html, "https://thinkrobotics.com/products/crius-pixhawk-i2c-splitter"
    )

    assert result.manufacturer is None


@pytest.mark.parametrize(
    ("title", "expected_category"),
    [
        ("Pixhawk Pro 6C Flight Controller", "Flight Controllers"),
        ("Raspberry Pi 5 8GB", "Companion Computers"),
        ("Jetson Orin NX Deployment Kit", "Companion Computers"),
        ("Raspberry Pi AI HAT+", "HATs & Carrier Boards"),
        ("Raspberry Pi Camera Module 3", "Other"),
        ("Raspberry Pi Official SD Card", "Other"),
        ("Raspberry Pi Pico", "Other"),
        ("M3 random frame screws", "Other"),
    ],
)
def test_product_categories_are_relevance_aware(title: str, expected_category: str) -> None:
    result = ThinkRoboticsAdapter().parse_product(
        f"<main><h1>{title}</h1><button>Add to cart</button></main>",
        "https://thinkrobotics.com/products/example",
    )

    assert result.category == expected_category


def test_thinkrobotics_fingerprint_changes_with_variant_price() -> None:
    html = (FIXTURES / "thinkrobotics_variants.html").read_text(encoding="utf-8")
    adapter = ThinkRoboticsAdapter()

    assert adapter.fingerprint(html) != adapter.fingerprint(html.replace("779999", "789999"))


def test_thinkrobotics_missing_price_stays_null() -> None:
    result = ThinkRoboticsAdapter().parse_product(
        "<main><h1>Pixhawk Flight Controller</h1><button>Sold out</button></main>",
        "https://thinkrobotics.com/products/pixhawk-flight-controller",
    )

    assert result.status is ProductStatus.OUT_OF_STOCK
    assert result.price is None


def test_thinkrobotics_product_main_sale_markup_uses_selling_price() -> None:
    result = ThinkRoboticsAdapter().parse_product(
        "<main><h1>Raspberry Pi AI HAT+</h1>"
        "<div class='product-main__price'><span>₹ 7,249.99</span>"
        "<s class='product-main__compare'>₹ 9,999.99</s></div>"
        "<button>Sold out</button></main>",
        "https://thinkrobotics.com/products/raspberry-pi-ai-hat",
    )

    assert result.status is ProductStatus.OUT_OF_STOCK
    assert str(result.price) == "7249.99"
    assert result.attributes["compare_at_price"] == "9999.99"
