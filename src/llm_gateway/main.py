"""Application factory. Uvicorn loads create_app as a factory."""

import uvicorn
from fastapi import FastAPI

from llm_gateway import __version__
from llm_gateway.api.routes import mount
from llm_gateway.cache.ledger import build_ledger
from llm_gateway.config import Settings
from llm_gateway.guardrails.engine import Sentinel
from llm_gateway.llm.langchain_client import LangChainClient
from llm_gateway.llm.relay import Relay
from llm_gateway.llm.service import GatewayService
from llm_gateway.observability.logging import setup_logging
from llm_gateway.observability.metrics import BeaconMetrics
from llm_gateway.observability.tracing import setup_tracing
from llm_gateway.routing.atlas import Atlas
from llm_gateway.security.airlock import Airlock
from llm_gateway.security.throttle import Throttle


def create_app(settings: Settings | None = None, llm=None, cache=None) -> FastAPI:
    settings = settings or Settings()
    settings.check()
    setup_logging(settings)
    setup_tracing(settings)
    metrics = BeaconMetrics()
    ledger = cache or build_ledger(settings)
    metrics.backend.labels(backend=ledger.backend).set(1)
    sentinel = Sentinel(
        enabled=settings.guardrails_enabled,
        block_on_secret=settings.block_on_secret,
        block_on_injection=settings.block_on_injection,
        redact_pii_enabled=settings.redact_pii,
    )
    service = GatewayService(
        settings=settings,
        sentinel=sentinel,
        atlas=Atlas(settings),
        relay=Relay(llm or LangChainClient(settings)),
        ledger=ledger,
        metrics=metrics,
    )
    docs = settings.docs_enabled()
    app = FastAPI(
        title="LLM Gateway",
        version=__version__,
        debug=False,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.ledger = ledger
    app.state.metrics = metrics
    app.state.service = service
    app.state.airlock = Airlock(settings)
    app.state.throttle = Throttle(settings.rate_limit_rpm)
    mount(app)
    return app


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "llm_gateway.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        server_header=False,
    )
