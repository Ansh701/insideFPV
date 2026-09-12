import hashlib
import uuid

from app.models import AlertEventType, ProductStatus


def favorable_event(
    previous: ProductStatus | None, current: ProductStatus
) -> AlertEventType | None:
    if previous is None:
        return None
    if current is ProductStatus.IN_STOCK and previous in {
        ProductStatus.OUT_OF_STOCK,
        ProductStatus.UNKNOWN,
        ProductStatus.PREORDER,
    }:
        return AlertEventType.BACK_IN_STOCK
    if current is ProductStatus.PREORDER and previous in {
        ProductStatus.OUT_OF_STOCK,
        ProductStatus.UNKNOWN,
    }:
        return AlertEventType.PREORDER_OPENED
    return None


def make_event_fingerprint(
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    previous_snapshot_id: uuid.UUID,
    previous: ProductStatus,
    current: ProductStatus,
    content_hash: str,
) -> str:
    material = ":".join(
        (
            str(user_id),
            str(product_id),
            str(previous_snapshot_id),
            previous.value,
            current.value,
            content_hash,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
