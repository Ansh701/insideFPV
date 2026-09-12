from datetime import datetime
from decimal import Decimal
from difflib import SequenceMatcher

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductStatus, Retailer


class SearchFilters(BaseModel):
    query: str | None = None
    category: str | None = None
    availability: ProductStatus | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    retailer: str | None = None
    manufacturer: str | None = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ProductSearchItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    retailer: str
    retailer_domain: str
    canonical_url: str
    manufacturer: str | None
    category: str
    status: ProductStatus
    price: Decimal | None
    currency: str
    attributes: dict[str, object]
    last_checked_at: datetime | None


class ProductSearchResult(BaseModel):
    items: list[ProductSearchItem]
    total: int
    limit: int
    offset: int
    suggestion: str | None = None


def _item(product: Product, retailer: Retailer) -> ProductSearchItem:
    return ProductSearchItem(
        id=str(product.id),
        name=product.name,
        retailer=retailer.name,
        retailer_domain=retailer.domain,
        canonical_url=product.canonical_url,
        manufacturer=product.manufacturer,
        category=product.category,
        status=product.current_status,
        price=product.current_price,
        currency=product.currency,
        attributes=product.attributes,
        last_checked_at=product.last_checked_at,
    )


class ProductSearchService:
    async def search(self, session: AsyncSession, filters: SearchFilters) -> ProductSearchResult:
        conditions = []
        if filters.query:
            token = f"%{filters.query.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(Product.name).like(token),
                    func.lower(Product.normalized_name).like(token),
                    func.lower(Product.manufacturer).like(token),
                )
            )
        if filters.category:
            conditions.append(func.lower(Product.category) == filters.category.lower())
        if filters.availability:
            conditions.append(Product.current_status == filters.availability)
        if filters.min_price is not None:
            conditions.append(Product.current_price >= filters.min_price)
        if filters.max_price is not None:
            conditions.append(Product.current_price <= filters.max_price)
        if filters.retailer:
            conditions.append(func.lower(Retailer.name) == filters.retailer.lower())
        if filters.manufacturer:
            conditions.append(func.lower(Product.manufacturer) == filters.manufacturer.lower())

        base = (
            select(Product, Retailer)
            .join(Retailer, Product.retailer_id == Retailer.id)
            .where(*conditions)
        )
        count_statement = select(func.count()).select_from(base.subquery())
        total = int(await session.scalar(count_statement) or 0)
        rows = (
            await session.execute(
                base.order_by(Product.name, Retailer.name)
                .offset(filters.offset)
                .limit(filters.limit)
            )
        ).all()
        items = [_item(product, retailer) for product, retailer in rows]
        suggestion: str | None = None
        if not items and filters.query:
            query_value = filters.query
            names = list((await session.scalars(select(Product.name))).all())
            query_tokens = query_value.lower().split()

            def score(name: str) -> float:
                name_tokens = name.lower().split()
                token_score = sum(
                    max(
                        SequenceMatcher(None, query_token, name_token).ratio()
                        for name_token in name_tokens
                    )
                    for query_token in query_tokens
                ) / len(query_tokens)
                full_score = SequenceMatcher(None, query_value.lower(), name.lower()).ratio()
                return max(token_score, full_score)

            scored = sorted(((score(name), name) for name in names), reverse=True)
            if scored and scored[0][0] >= 0.45:
                suggestion = scored[0][1]
        return ProductSearchResult(
            items=items,
            total=total,
            limit=filters.limit,
            offset=filters.offset,
            suggestion=suggestion,
        )
