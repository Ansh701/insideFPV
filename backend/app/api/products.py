import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Product, ProductSnapshot, ProductStatus
from app.services.search import ProductSearchResult, ProductSearchService, SearchFilters

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductSearchResult)
async def list_products(
    query: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=120),
    availability: ProductStatus | None = None,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    retailer: str | None = Query(default=None, max_length=80),
    manufacturer: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ProductSearchResult:
    return await ProductSearchService().search(
        session,
        SearchFilters(
            query=query,
            category=category,
            availability=availability,
            min_price=min_price,
            max_price=max_price,
            retailer=retailer,
            manufacturer=manufacturer,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/{product_id}")
async def get_product(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    product = await session.scalar(
        select(Product).options(selectinload(Product.retailer)).where(Product.id == product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return {
        "id": product.id,
        "name": product.name,
        "retailer": product.retailer.name,
        "canonical_url": product.canonical_url,
        "manufacturer": product.manufacturer,
        "category": product.category,
        "status": product.current_status,
        "price": product.current_price,
        "currency": product.currency,
        "attributes": product.attributes,
        "last_checked_at": product.last_checked_at,
        "first_seen_at": product.first_seen_at,
    }


@router.get("/{product_id}/history")
async def get_history(
    product_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    if await session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    rows = list(
        (
            await session.scalars(
                select(ProductSnapshot)
                .where(ProductSnapshot.product_id == product_id)
                .order_by(ProductSnapshot.checked_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "status": row.status,
                "price": row.price,
                "currency": row.currency,
                "classification_source": row.classification_source,
                "classification_provider": row.classification_provider,
                "confidence": row.confidence,
                "checked_at": row.checked_at,
                "error": row.error,
            }
            for row in rows
        ]
    }
