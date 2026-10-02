from llm_gateway.observability.redaction import redact_event
from llm_gateway.observability.timer import Chronos


def test_timer_records_a_stage_and_total():
    clock = Chronos()
    with clock.stage("guardrails"):
        pass
    snapshot = clock.snapshot()
    assert "guardrails" in snapshot
    assert snapshot["total"] >= snapshot["guardrails"]


def test_log_events_do_not_keep_secrets_or_email():
    event = redact_event(
        None,
        None,
        {"event": "generate", "detail": "AKIAIOSFODNN7EXAMPLE ada@example.com"},
    )
    assert "AKIA" not in event["detail"]
    assert "ada@example.com" not in event["detail"]
    assert "[REDACTED_SECRET]" in event["detail"]
    assert "[REDACTED_EMAIL]" in event["detail"]
