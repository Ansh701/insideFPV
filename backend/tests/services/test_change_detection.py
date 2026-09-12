import uuid

import pytest

from app.models import ProductStatus
from app.services.change_detection import favorable_event, make_event_fingerprint


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (None, ProductStatus.IN_STOCK, None),
        (ProductStatus.OUT_OF_STOCK, ProductStatus.IN_STOCK, "BACK_IN_STOCK"),
        (ProductStatus.UNKNOWN, ProductStatus.IN_STOCK, "BACK_IN_STOCK"),
        (ProductStatus.OUT_OF_STOCK, ProductStatus.PREORDER, "PREORDER_OPENED"),
        (ProductStatus.UNKNOWN, ProductStatus.PREORDER, "PREORDER_OPENED"),
        (ProductStatus.PREORDER, ProductStatus.IN_STOCK, "BACK_IN_STOCK"),
        (ProductStatus.IN_STOCK, ProductStatus.IN_STOCK, None),
        (ProductStatus.OUT_OF_STOCK, ProductStatus.OUT_OF_STOCK, None),
    ],
)
def test_change_detection_only_emits_favorable_non_baseline_transitions(
    previous: ProductStatus | None,
    current: ProductStatus,
    expected: str | None,
) -> None:
    event = favorable_event(previous, current)
    assert (event.value if event else None) == expected


def test_retried_monitoring_event_has_same_alert_fingerprint() -> None:
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    product_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    previous_snapshot_id = uuid.UUID("00000000-0000-0000-0000-000000000003")

    first = make_event_fingerprint(
        user_id,
        product_id,
        previous_snapshot_id,
        ProductStatus.OUT_OF_STOCK,
        ProductStatus.IN_STOCK,
        "same-page-hash",
    )
    retried = make_event_fingerprint(
        user_id,
        product_id,
        previous_snapshot_id,
        ProductStatus.OUT_OF_STOCK,
        ProductStatus.IN_STOCK,
        "same-page-hash",
    )

    assert first == retried
    assert len(first) == 64
