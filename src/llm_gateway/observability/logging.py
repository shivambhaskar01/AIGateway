"""Beacon logs: JSON lines, request id, and redaction before the renderer."""

import logging
from contextvars import ContextVar

import structlog

from llm_gateway.observability.redaction import redact_event

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def _add_request_id(_logger, _method, event_dict: dict) -> dict:
    event_dict.setdefault("request_id", request_id_var.get())
    return event_dict


def setup_logging(settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_event,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=False,
    )


def get_logger():
    return structlog.get_logger()
