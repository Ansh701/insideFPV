import asyncio
import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class UnsafeUrlError(ValueError):
    pass


TRACKING_KEYS = {"gclid", "fbclid", "ref", "source"}
ALLOWED_PORTS = {None, 80, 443}


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # is_global correctly accepts the well-known NAT64 prefix used by some
    # public DNS resolvers while excluding loopback, private, link-local,
    # documentation, unspecified, and metadata-service ranges.
    return address.is_global and not address.is_multicast


def normalize_supported_url(url: str, allowed_domains: set[str]) -> str:
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrlError("The product URL is malformed.") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeUrlError("Only HTTP and HTTPS product URLs are accepted.")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("Product URLs cannot contain credentials.")
    if port not in ALLOWED_PORTS:
        raise UnsafeUrlError("Non-standard URL ports are not accepted.")
    host = (parsed.hostname or "").lower().removeprefix("www.").rstrip(".")
    if not host or host == "localhost":
        raise UnsafeUrlError("A supported public retailer hostname is required.")
    try:
        if not _is_public_address(host):
            raise UnsafeUrlError("Private and local network addresses are not accepted.")
    except ValueError:
        pass
    if host not in allowed_domains:
        raise UnsafeUrlError("This retailer is not supported.")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = "/" + "/".join(part for part in parsed.path.split("/") if part)
    return urlunsplit((parsed.scheme.lower(), host, path or "/", urlencode(query), ""))


async def validate_public_resolution(hostname: str, port: int) -> None:
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo, hostname, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError("The retailer hostname could not be resolved.") from exc
    addresses = {str(record[4][0]) for record in records}
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise UnsafeUrlError("The retailer hostname must resolve only to a public network address.")
