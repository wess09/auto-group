"""Audit HTTP security/upload requests, including dependency and validation failures."""

import time
import secrets

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError

from app.services import admin_accounts, audit
from app.services.admin.runtime import database


class AuditedRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def audited(request: Request):
            started = time.perf_counter()
            request.state.audit_request_id = secrets.token_hex(12)
            params = {}
            if "application/json" in request.headers.get("content-type", ""):
                try:
                    body = await request.json()
                    if isinstance(body, dict):
                        params = body
                except ValueError:
                    pass
            actor = None
            authorization = request.headers.get("authorization", "")
            if authorization.startswith("Bearer "):
                try:
                    actor = await database(admin_accounts.profile, authorization[7:].strip())
                except HTTPException:
                    pass
            fields = audit.request_context(actor, request)
            if actor is None:
                fields["actor_username"] = str(params.get("username", ""))[:64]
            code = 500
            try:
                with audit.scope(fields):
                    response = await handler(request)
                code = response.status_code
                return response
            except HTTPException as exc:
                code = exc.status_code
                raise
            except RequestValidationError:
                code = 422
                raise
            finally:
                authenticated_actor = getattr(request.state, "audit_actor", None)
                if authenticated_actor is not None:
                    fields = audit.request_context(authenticated_actor, request)
                # Never inspect response bodies: they may contain JWTs or TOTP secrets.
                await database(
                    audit.record,
                    "http." + request.url.path.removeprefix("/api/").replace("/", "."),
                    details={"method": request.method, "params": params, "status_code": code},
                    status="success" if code < 400 else "failed",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    **fields,
                )

        return audited
