import secrets

from fastapi import Header, HTTPException, Request


async def require_admin(
    request: Request,
    x_admin_secret: str | None = Header(default=None),
) -> None:
    expected = request.app.state.settings.admin_secret
    if not x_admin_secret or not secrets.compare_digest(x_admin_secret, expected):
        raise HTTPException(status_code=401, detail="A valid admin secret is required.")
