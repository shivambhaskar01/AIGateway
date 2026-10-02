"""Beacon metrics. Each app gets its own registry so tests do not collide."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class BeaconMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.http = Counter(
            "llm_gateway_http_requests_total",
            "HTTP responses",
            ["path", "status"],
            registry=self.registry,
        )
        self.generations = Counter(
            "llm_gateway_generations_total",
            "Generation outcomes",
            ["status", "route", "cache", "model"],
            registry=self.registry,
        )
        self.findings = Counter(
            "llm_gateway_guardrail_findings_total",
            "Guardrail findings",
            ["kind", "name", "action"],
            registry=self.registry,
        )
        self.cache_errors = Counter(
            "llm_gateway_cache_errors_total",
            "Cache backend errors",
            ["op"],
            registry=self.registry,
        )
        self.stage = Histogram(
            "llm_gateway_stage_seconds",
            "Stage latency",
            ["stage"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
            registry=self.registry,
        )
        self.backend = Gauge(
            "llm_gateway_cache_backend_info",
            "Active cache backend",
            ["backend"],
            registry=self.registry,
        )

    def record(self, *, status: str, route: str, cache: str, model: str, findings, timing: dict) -> None:
        self.generations.labels(status=status, route=route, cache=cache, model=model).inc()
        for finding in findings:
            self.findings.labels(kind=finding.kind, name=finding.name, action=finding.action).inc()
        for name, elapsed_ms in timing.items():
            self.stage.labels(stage=name).observe(elapsed_ms / 1000)
