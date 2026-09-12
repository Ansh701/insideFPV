def public_check_error(error: str | None) -> str | None:
    """Map persisted diagnostic detail to stable, user-safe product guidance."""
    if not error:
        return None
    lowered = error.lower()
    if "http 403" in lowered or "forbidden" in lowered:
        return "The retailer blocked the automated request (HTTP 403)."
    if "timed out" in lowered or "timeout" in lowered:
        return "The retailer did not respond before the request timed out."
    if "redirected too many" in lowered or "too many redirects" in lowered:
        return "The retailer redirected the request too many times."
    if "http 404" in lowered or "not found" in lowered:
        return "The retailer product page was not found (HTTP 404)."
    if "safe size limit" in lowered:
        return "The retailer response was too large to process safely."
    if "llm" in lowered or "provider" in lowered:
        return "The page was ambiguous and the AI fallback was unavailable."
    return "The retailer response could not be processed."
