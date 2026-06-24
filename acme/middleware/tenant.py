"""Tenant context and optional API-key authentication."""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from acme.config import settings

TENANT_HEADER = "X-Tenant-ID"
API_KEY_HEADER = "X-API-Key"


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        tenant_id = request.headers.get(TENANT_HEADER, settings.default_tenant_id)
        request.state.tenant_id = tenant_id.strip() or settings.default_tenant_id
        return await call_next(request)


def verify_api_key(request: Request) -> None:
    if not settings.api_key:
        return
    provided = request.headers.get(API_KEY_HEADER, "")
    if provided != settings.api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid or missing API key")
