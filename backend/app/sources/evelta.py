import re

from bs4 import BeautifulSoup

from app.models import ProductStatus
from app.sources.base import RetailerAdapter


class EveltaAdapter(RetailerAdapter):
    name = "Evelta"
    domain = "evelta.com"

    def status_from_soup(self, soup: BeautifulSoup) -> ProductStatus | None:
        text = soup.get_text(" ", strip=True).lower()
        if re.search(r"\b(pre[- ]?order|available on backorder)\b", text):
            return ProductStatus.PREORDER
        if re.search(r"\b(out of stock|sold out)\b", text):
            return ProductStatus.OUT_OF_STOCK
        quantity = re.search(r"\b(?:only\s+)?(\d+)\s+in stock\b", text)
        if quantity:
            return (
                ProductStatus.IN_STOCK if int(quantity.group(1)) > 0 else ProductStatus.OUT_OF_STOCK
            )
        return None
