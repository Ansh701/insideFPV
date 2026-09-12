import hashlib
import json
import re
from abc import ABC
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field

from app.models import ProductStatus


class ProductExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProductStatus
    product_name: str | None = None
    price: Decimal | None = None
    currency: str = "INR"
    manufacturer: str | None = None
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    compatibility: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    classification_source: str = "DETERMINISTIC"
    provider: str | None = None


class FetchedProduct(BaseModel):
    extraction: ProductExtraction
    normalized_content: str
    content_hash: str


AVAILABILITY_MAP = {
    "instock": ProductStatus.IN_STOCK,
    "limitedavailability": ProductStatus.IN_STOCK,
    "outofstock": ProductStatus.OUT_OF_STOCK,
    "soldout": ProductStatus.OUT_OF_STOCK,
    "preorder": ProductStatus.PREORDER,
    "presale": ProductStatus.PREORDER,
    "backorder": ProductStatus.PREORDER,
}


def _decimal(value: object, *, minor_units: bool = False) -> Decimal | None:
    if value is None:
        return None
    raw = re.sub(r"[^0-9.]", "", str(value))
    if not raw:
        return None
    try:
        result = Decimal(raw)
        return result / 100 if minor_units else result
    except InvalidOperation:
        return None


def _availability(value: object) -> ProductStatus | None:
    if not value:
        return None
    token = re.sub(r"[^a-z]", "", str(value).rsplit("/", 1)[-1].lower())
    return AVAILABILITY_MAP.get(token)


def _product_nodes(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [node for item in value for node in _product_nodes(item)]
    if not isinstance(value, dict):
        return []
    nodes: list[dict[str, Any]] = []
    type_value = value.get("@type")
    types = type_value if isinstance(type_value, list) else [type_value]
    if any(str(item).lower() == "product" for item in types):
        nodes.append(value)
    if "@graph" in value:
        nodes.extend(_product_nodes(value["@graph"]))
    return nodes


def infer_category(name: str | None) -> str | None:
    lowered = (name or "").lower()
    if any(term in lowered for term in ("hat", "carrier board", "baseboard")):
        return "HATs & Carrier Boards"
    if any(term in lowered for term in ("flight controller", "pixhawk", "autopilot")):
        return "Flight Controllers"
    if any(term in lowered for term in ("raspberry pi", "jetson", "companion computer")):
        return "Companion Computers"
    return None


class RetailerAdapter(ABC):
    name: str
    domain: str

    def can_handle(self, url: str) -> bool:
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        return host == self.domain

    def parse_product(self, html: str, url: str) -> ProductExtraction:
        soup = BeautifulSoup(html, "lxml")
        structured = self._structured_product(soup)
        if structured:
            return structured
        return self._deterministic_product(soup, url)

    def normalize_content(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for element in soup.select("script, style, nav, header, footer, aside, noscript, svg"):
            element.decompose()
        return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:12000]

    def fingerprint(self, html: str) -> str:
        return hashlib.sha256(self.normalize_content(html).encode("utf-8")).hexdigest()

    def discover_products(self, html: str, source_url: str, limit: int = 50) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        result: list[str] = []
        for anchor in soup.select("a[href*='/product/'], a[href*='/products/']"):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            if href.startswith("/"):
                href = f"https://{self.domain}{href}"
            if self.can_handle(href):
                canonical = href.split("#", 1)[0]
                if canonical not in result:
                    result.append(canonical)
            if len(result) >= limit:
                break
        return result

    def _structured_product(self, soup: BeautifulSoup) -> ProductExtraction | None:
        for script in soup.select("script[type='application/ld+json']"):
            try:
                payload = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            for product in _product_nodes(payload):
                offers = product.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if not isinstance(offers, dict):
                    offers = {}
                status = _availability(offers.get("availability"))
                name = str(product.get("name") or "").strip() or None
                if status is None:
                    status = self.status_from_soup(soup)
                if status is None:
                    status = ProductStatus.UNKNOWN
                brand = product.get("brand")
                manufacturer = brand.get("name") if isinstance(brand, dict) else brand
                evidence = [str(offers.get("availability"))] if offers.get("availability") else []
                return ProductExtraction(
                    status=status,
                    product_name=name,
                    price=_decimal(offers.get("price") or product.get("price")),
                    currency=str(offers.get("priceCurrency") or "INR")[:3].upper(),
                    manufacturer=str(manufacturer) if manufacturer else None,
                    category=str(product.get("category") or infer_category(name) or "Other"),
                    attributes={"sku": str(product["sku"])} if product.get("sku") else {},
                    confidence=0.98
                    if evidence
                    else (0.86 if status is not ProductStatus.UNKNOWN else 0.4),
                    evidence=evidence or ["structured Product data without explicit availability"],
                )
        return self._embedded_product_json(soup)

    def _embedded_product_json(self, soup: BeautifulSoup) -> ProductExtraction | None:
        for script in soup.select("script[type='application/json']"):
            try:
                value = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(value, dict) or not value.get("title") or "available" not in value:
                continue
            price = value.get("price")
            variants = value.get("variants")
            if isinstance(variants, list) and variants:
                selected = next((item for item in variants if item.get("available")), variants[0])
                price = selected.get("price", price)
                sku = selected.get("sku")
            else:
                sku = value.get("sku")
            status = (
                ProductStatus.IN_STOCK if value.get("available") else ProductStatus.OUT_OF_STOCK
            )
            title = str(value["title"])
            return ProductExtraction(
                status=status,
                product_name=title,
                price=_decimal(price, minor_units=True),
                manufacturer=str(value.get("vendor") or "") or None,
                category=str(value.get("type") or infer_category(title) or "Other"),
                attributes={"sku": str(sku)} if sku else {},
                confidence=0.98,
                evidence=[f"embedded available={str(value.get('available')).lower()}"],
            )
        return None

    def _deterministic_product(self, soup: BeautifulSoup, url: str) -> ProductExtraction:
        heading = soup.select_one("h1")
        name = heading.get_text(" ", strip=True) if heading else None
        price_node = soup.select_one(".price, [itemprop='price']")
        price = _decimal(price_node.get_text(" ", strip=True) if price_node else None)
        status = self.status_from_soup(soup) or ProductStatus.UNKNOWN
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        confidence = 0.9 if status is not ProductStatus.UNKNOWN else 0.3
        return ProductExtraction(
            status=status,
            product_name=name,
            price=price,
            category=infer_category(name) or "Other",
            confidence=confidence,
            evidence=[text[:500]]
            if text
            else [f"No usable product evidence at {urlsplit(url).path}"],
        )

    def status_from_soup(self, soup: BeautifulSoup) -> ProductStatus | None:
        text = soup.get_text(" ", strip=True).lower()
        if re.search(r"\b(pre[- ]?order|available on backorder)\b", text):
            return ProductStatus.PREORDER
        if re.search(r"\b(out of stock|sold out|currently unavailable)\b", text):
            return ProductStatus.OUT_OF_STOCK
        if re.search(r"\b(in stock|add to cart|ready to ship)\b", text):
            return ProductStatus.IN_STOCK
        return None
