"""Request pipeline: Sentinel, Atlas, Ledger, Relay, then Chronos on every exit."""

import hashlib
from dataclasses import dataclass

from opentelemetry.trace import Span

from llm_gateway.cache.ledger import cache_key
from llm_gateway.config import Settings
from llm_gateway.errors import GatewayError
from llm_gateway.guardrails.engine import Sentinel
from llm_gateway.llm.relay import ProviderFailure, Relay
from llm_gateway.observability.logging import get_logger, request_id_var
from llm_gateway.observability.timer import Chronos
from llm_gateway.observability.tracing import tracer
from llm_gateway.routing.atlas import Atlas


@dataclass(frozen=True)
class Command:
    prompt: str
    tier: str
    model: str | None
    temperature: float
    max_tokens: int
    use_cache: bool


@dataclass(frozen=True)
class Generation:
    status_code: int
    body: dict


class GatewayService:
    def __init__(self, settings: Settings, sentinel: Sentinel, atlas: Atlas, relay: Relay, ledger, metrics) -> None:
        self.settings = settings
        self.sentinel = sentinel
        self.atlas = atlas
        self.relay = relay
        self.ledger = ledger
        self.metrics = metrics

    async def generate(self, command: Command) -> Generation:
        chrono = Chronos()
        prompt_hash = hashlib.sha256(command.prompt.encode()).hexdigest()
        route_name = "none"
        cache_state = "skipped"
        model_name = "none"
        findings = ()
        try:
            if len(command.prompt) > self.settings.max_prompt_chars:
                raise GatewayError(413, "payload_too_large")

            with tracer().start_as_current_span("sentinel") as span:
                with chrono.stage("guardrails"):
                    verdict = self.sentinel.scan_input(command.prompt)
                findings = verdict.findings
                _attr(span, "llm_gateway.guardrail_action", verdict.action)

            if verdict.action == "block":
                timing = self._record("blocked", route_name, cache_state, model_name, findings, chrono)
                self._log("generate.blocked", prompt_hash, cache_state, route_name, model_name)
                raise GatewayError(
                    400,
                    "policy_blocked",
                    extra=self._meta(prompt_hash, timing, cache_state, {"guardrails": verdict.as_dict()}),
                )

            with tracer().start_as_current_span("atlas") as span:
                with chrono.stage("routing"):
                    route = self.atlas.route(verdict.text, command.tier, command.model)
                route_name = route.tier
                _attr(span, "llm_gateway.route", route.tier)

            cached = None
            key = None
            if command.use_cache:
                key = cache_key(
                    tier=route.tier,
                    models=route.models,
                    prompt=verdict.text,
                    temperature=command.temperature,
                    max_tokens=command.max_tokens,
                )
                with tracer().start_as_current_span("ledger") as span:
                    with chrono.stage("cache"):
                        cached = self._read_cache(key)
                    cache_state = "hit" if cached else "miss"
                    _attr(span, "llm_gateway.cache", cache_state)
            else:
                cache_state = "bypass"

            if cached:
                model_name = cached["model"]
                timing = self._record("ok", route_name, cache_state, model_name, findings, chrono)
                body = self._success(prompt_hash, timing, cache_state, verdict, route, cached, cached["attempts"])
                return Generation(200, body)

            with tracer().start_as_current_span("relay"):
                with chrono.stage("model"):
                    result = await self.relay.run(
                        route.models,
                        prompt=verdict.text,
                        temperature=command.temperature,
                        max_tokens=command.max_tokens,
                        timeout=self.settings.request_timeout_seconds,
                    )
            model_name = result.model

            with tracer().start_as_current_span("sentinel_egress"):
                with chrono.stage("egress"):
                    egress = self.sentinel.scan_output(result.output)
            if egress.action == "block":
                findings = findings + egress.findings
                timing = self._record("blocked", route_name, cache_state, model_name, findings, chrono)
                raise GatewayError(
                    502,
                    "output_policy_blocked",
                    extra=self._meta(prompt_hash, timing, cache_state, {"guardrails": egress.as_dict()}),
                )

            stored = {
                "output": egress.text,
                "model": result.model,
                "route": route.tier,
                "route_reason": route.reason,
                "fallback_used": result.fallback_used,
                "attempts": list(result.attempts),
            }
            if key is not None:
                self._write_cache(key, stored)
            timing = self._record("ok", route_name, cache_state, model_name, findings, chrono)
            self._log("generate.complete", prompt_hash, cache_state, route_name, model_name)
            return Generation(200, self._success(prompt_hash, timing, cache_state, verdict, route, stored, stored["attempts"]))
        except ProviderFailure as exc:
            timing = self._record("error", route_name, cache_state, model_name, findings, chrono)
            raise GatewayError(
                503,
                exc.code,
                extra=self._meta(prompt_hash, timing, cache_state, {"attempts": exc.attempts}),
            ) from None
        except GatewayError as exc:
            if "timing_ms" not in exc.extra:
                timing = self._record("error", route_name, cache_state, model_name, findings, chrono)
                exc.extra = self._meta(prompt_hash, timing, cache_state, exc.extra)
            raise

    def _read_cache(self, key: str):
        try:
            return self.ledger.get(key)
        except Exception as exc:
            self.metrics.cache_errors.labels(op="get").inc()
            get_logger().warning("ledger.read_failed", error_type=type(exc).__name__)
            return None

    def _write_cache(self, key: str, value: dict) -> None:
        try:
            self.ledger.set(key, value)
        except Exception as exc:
            self.metrics.cache_errors.labels(op="set").inc()
            get_logger().warning("ledger.write_failed", error_type=type(exc).__name__)

    def _record(self, status, route, cache, model, findings, chrono) -> dict:
        timing = chrono.snapshot()
        self.metrics.record(status=status, route=route, cache=cache, model=model, findings=findings, timing=timing)
        return timing

    def _meta(self, prompt_hash: str, timing: dict, cache_state: str, extra: dict) -> dict:
        body = {"id": request_id_var.get(), "prompt_sha256": prompt_hash, "cache": cache_state, "timing_ms": timing}
        body.update(extra)
        return body

    def _success(self, prompt_hash, timing, cache_state, verdict, route, stored, attempts) -> dict:
        body = self._meta(prompt_hash, timing, cache_state, {})
        body.update(
            {
                "output": stored["output"],
                "model": stored["model"],
                "route": stored.get("route", route.tier),
                "route_reason": stored.get("route_reason", route.reason),
                "fallback_used": stored["fallback_used"],
                "attempts": attempts,
                "guardrails": verdict.as_dict(),
                "forwarded_prompt": verdict.text,
            }
        )
        return body

    def _log(self, event: str, prompt_hash: str, cache_state: str, route: str, model: str) -> None:
        get_logger().info(event, prompt_sha256=prompt_hash, cache=cache_state, route=route, model=model)


def _attr(span: Span, key: str, value: str) -> None:
    span.set_attribute(key, value)
