import json
from decimal import Decimal
from typing import Any

from bs4 import BeautifulSoup

from app.models import ProductStatus
from app.sources.base import ProductExtraction, RetailerAdapter, _decimal, infer_category


class ThinkRoboticsAdapter(RetailerAdapter):
    name = "ThinkRobotics"
    domain = "thinkrobotics.com"

    def normalize_content(self, html: str) -> str:
        """Include compact commerce fields in the hash without retaining page scripts."""
        visible = super().normalize_content(html)
        soup = BeautifulSoup(html, "lxml")
        commerce: list[dict[str, Any]] = []
        for script in soup.select("script[type='application/json']"):
            try:
                value = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            values = (
                value
                if isinstance(value, list)
                else value.get("variants", [])
                if isinstance(value, dict)
                else []
            )
            if not isinstance(values, list):
                continue
            commerce.extend(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "available": item.get("available"),
                    "price": item.get("price"),
                    "compare_at_price": item.get("compare_at_price"),
                }
                for item in values
                if isinstance(item, dict) and "available" in item
            )
        suffix = json.dumps(commerce, sort_keys=True, separators=(",", ":"))
        return f"{visible[:10000]} {suffix}"[:12000]

    def _embedded_product_json(self, soup: BeautifulSoup) -> ProductExtraction | None:
        product: dict[str, Any] | None = None
        variants: list[dict[str, Any]] = []
        for script in soup.select("script[type='application/json']"):
            try:
                value = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(value, dict) and value.get("title") and "available" in value:
                product = value
                embedded_variants = value.get("variants")
                if isinstance(embedded_variants, list):
                    variants = [item for item in embedded_variants if isinstance(item, dict)]
            elif (
                isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
            ):
                candidates = [
                    item
                    for item in value
                    if isinstance(item, dict) and "available" in item and "price" in item
                ]
                if candidates:
                    variants = candidates

        if product is None and not variants:
            return None

        heading = soup.select_one("main h1, h1")
        title = str(product.get("title") if product else "").strip()
        if not title and heading is not None:
            title = heading.get_text(" ", strip=True)
        if not title:
            return None

        selected = self._selected_variant(soup, variants)
        price_value = selected.get("price") if selected else (product or {}).get("price")
        price = self._shopify_money(price_value)
        any_available = any(bool(item.get("available")) for item in variants)
        available = any_available if variants else bool((product or {}).get("available"))
        product_text = (soup.select_one("main") or soup).get_text(" ", strip=True).lower()
        if "pre-order" in product_text or "pre order" in product_text:
            status = ProductStatus.PREORDER
        else:
            status = ProductStatus.IN_STOCK if available else ProductStatus.OUT_OF_STOCK

        attributes: dict[str, Any] = {}
        if variants:
            attributes["variants"] = [self._variant_attribute(item) for item in variants]
        if selected:
            variant_name = str(selected.get("title") or "").strip()
            if variant_name:
                attributes["selected_variant"] = variant_name
            sku = str(selected.get("sku") or "").strip()
            if sku:
                attributes["sku"] = sku
            compare_at = self._shopify_money(selected.get("compare_at_price"))
            if compare_at is not None and price is not None and compare_at > price:
                attributes["compare_at_price"] = str(compare_at)

        product_type = str((product or {}).get("type") or "").strip() or None
        return ProductExtraction(
            status=status,
            product_name=title,
            price=price,
            currency="INR",
            manufacturer=self._manufacturer(soup, product),
            category=infer_category(title, product_type) or "Other",
            attributes=attributes,
            confidence=0.98,
            evidence=[
                f"Shopify variants={len(variants)}",
                f"purchasable={str(available).lower()}",
            ],
        )

    def _deterministic_product(self, soup: BeautifulSoup, url: str) -> ProductExtraction:
        result = super()._deterministic_product(soup, url)
        price_container = soup.select_one("main .product-main__price")
        if price_container is not None:
            selling_node = price_container.select_one(":scope > span")
            selling_price = _decimal(
                selling_node.get_text(" ", strip=True) if selling_node else None
            )
            if selling_price is not None:
                result.price = selling_price
            compare_node = price_container.select_one(":scope > s")
            compare_at = _decimal(compare_node.get_text(" ", strip=True) if compare_node else None)
            if compare_at is not None and result.price is not None and compare_at > result.price:
                result.attributes["compare_at_price"] = str(compare_at)
        result.manufacturer = self._manufacturer(soup, None)
        return result

    @staticmethod
    def _selected_variant(
        soup: BeautifulSoup, variants: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        if not variants:
            return None
        selected_input = soup.select_one("main form[action*='/cart/add'] input[name='id']")
        selected_id = selected_input.get("value") if selected_input else None
        if selected_id is not None:
            match = next(
                (item for item in variants if str(item.get("id")) == str(selected_id)), None
            )
            if match is not None:
                return match
        return variants[0]

    @staticmethod
    def _shopify_money(value: object) -> Decimal | None:
        if value is None:
            return None
        raw = str(value).strip()
        minor_units = isinstance(value, int) or raw.isdigit()
        return _decimal(value, minor_units=minor_units)

    @classmethod
    def _variant_attribute(cls, variant: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": str(variant.get("title") or "Default"),
            "available": bool(variant.get("available")),
        }
        price = cls._shopify_money(variant.get("price"))
        if price is not None:
            result["price"] = str(price)
        compare_at = cls._shopify_money(variant.get("compare_at_price"))
        if compare_at is not None and price is not None and compare_at > price:
            result["compare_at_price"] = str(compare_at)
        sku = str(variant.get("sku") or "").strip()
        if sku:
            result["sku"] = sku
        return result

    @staticmethod
    def _manufacturer(soup: BeautifulSoup, product: dict[str, Any] | None) -> str | None:
        vendor = str((product or {}).get("vendor") or "").strip()
        if not vendor:
            node = soup.select_one("main a[href*='/collections/vendors']")
            vendor = node.get_text(" ", strip=True) if node else ""
        if vendor.lower().replace(" ", "") == "thinkrobotics":
            return None
        return vendor or None
