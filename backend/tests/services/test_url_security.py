import socket

import pytest

from app.services.url_security import (
    UnsafeUrlError,
    normalize_supported_url,
    validate_public_resolution,
)


def test_supported_url_is_canonicalized_and_tracking_parameters_removed() -> None:
    value = normalize_supported_url(
        "HTTPS://WWW.ROBU.IN/product/pi-5/?utm_source=mail&variant=8gb#reviews",
        {"robu.in"},
    )

    assert value == "https://robu.in/product/pi-5?variant=8gb"


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "file:///etc/passwd",
        "ftp://robu.in/product/a",
        "http://localhost/product/a",
        "http://127.0.0.1/product/a",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/product/a",
        "https://evil.example/product/a",
        "https://user:password@robu.in/product/a",
        "https://robu.in:444/product/a",
    ],
)
def test_unsafe_or_unsupported_product_url_is_rejected(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        normalize_supported_url(url, {"robu.in", "zbotic.in"})


@pytest.mark.asyncio
async def test_dns_resolution_rejects_private_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*_: object, **__: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.2", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UnsafeUrlError, match="public network"):
        await validate_public_resolution("robu.in", 443)


@pytest.mark.asyncio
async def test_dns_resolution_accepts_public_nat64_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*_: object, **__: object) -> list[tuple[object, ...]]:
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::17e3:2620", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("23.227.38.32", 443)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    await validate_public_resolution("thinkrobotics.com", 443)
