"""HTTP surface for LLM Gateway."""

import re
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from llm_gateway import __version__
from llm_gateway.api.schemas import GenerateIn
from llm_gateway.errors import GatewayError
from llm_gateway.llm.service import Command
from llm_gateway.observability.logging import get_logger, request_id_var

router = APIRouter()
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def mount(app) -> None:
    from fastapi.exceptions import RequestValidationError

    @app.middleware("http")
    async def context(request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        request_id = incoming if incoming and _REQUEST_ID.fullmatch(incoming) else uuid4().hex
        token = request_id_var.set(request_id)
        path = request.url.path
        try:
            response = await call_next(request)
            route = request.scope.get("route")
            path = getattr(route, "path", path)
            request.app.state.metrics.http.labels(path=path, status=str(response.status_code)).inc()
        finally:
            request_id_var.reset(token)
        response.headers["x-request-id"] = request_id
        response.headers["cache-control"] = "no-store"
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        return response

    @app.exception_handler(GatewayError)
    async def gateway_error(_request: Request, exc: GatewayError):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.code, **exc.extra})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError):
        fields = sorted(".".join(str(part) for part in err.get("loc", ())) for err in exc.errors())
        get_logger().info("request.invalid", fields=fields)
        return JSONResponse(status_code=422, content={"error": "invalid_request"})

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception):
        get_logger().error("request.failed", error_type=type(exc).__name__)
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    app.include_router(router)


@router.get("/")
def index():
    return {
        "name": "LLM Gateway",
        "version": __version__,
        "features": ["Airlock", "Throttle", "Sentinel", "Atlas", "Ledger", "Relay", "Chronos", "Beacon"],
    }


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request):
    return {"status": "ok", "cache_backend": request.app.state.ledger.backend}


@router.get("/metrics")
def metrics(request: Request):
    payload = generate_latest(request.app.state.metrics.registry)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@router.post("/v1/generate")
async def generate(body: GenerateIn, request: Request):
    _authorize(request)
    result = await request.app.state.service.generate(
        Command(
            prompt=body.prompt,
            tier=body.tier,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            use_cache=body.cache,
        )
    )
    response = JSONResponse(status_code=result.status_code, content=result.body)
    timing = result.body.get("timing_ms", {})
    if "total" in timing:
        response.headers["x-llm-gateway-total-ms"] = str(timing["total"])
    if "cache" in result.body:
        response.headers["x-llm-gateway-cache"] = str(result.body["cache"])
    return response


def _authorize(request: Request) -> None:
    airlock = request.app.state.airlock
    throttle = request.app.state.throttle
    token = airlock.bearer(request.headers.get("authorization"))
    if not throttle.allow(f"ip:{airlock.client_ip(request)}"):
        raise GatewayError(429, "rate_limited")
    if not airlock.verify(token):
        raise GatewayError(401, "unauthorized")
    if token is None or not throttle.allow(f"key:{airlock.fingerprint(token)}"):
        raise GatewayError(429, "rate_limited")
