"""Beacon traces. Spans go to structured logs, and to OTLP when configured."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult, SpanExporter

from llm_gateway.observability.logging import get_logger

_ready = False


class StructlogSpanExporter(SpanExporter):
    def export(self, spans):
        log = get_logger()
        for span in spans:
            start = span.start_time or 0
            end = span.end_time or start
            log.debug(
                "span",
                span_name=span.name,
                trace_id=format(span.context.trace_id, "032x"),
                duration_ms=round((end - start) / 1_000_000, 2),
                status=span.status.status_code.name,
            )
        return SpanExportResult.SUCCESS

    def shutdown(self):
        return None


def setup_tracing(settings) -> None:
    global _ready
    if _ready:
        return
    log = get_logger()
    try:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(StructlogSpanExporter()))
        if settings.otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint))
            )
        trace.set_tracer_provider(provider)
    except Exception as exc:
        log.warning("beacon.tracing_disabled", error_type=type(exc).__name__)
    _ready = True


def tracer():
    return trace.get_tracer("llm_gateway")
