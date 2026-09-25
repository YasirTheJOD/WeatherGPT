"""Request-ID propagation and structured log formatting (Phase 6 observability)."""

import json
import logging

from app.core.logging import (
    JsonFormatter,
    get_request_id,
    log_event,
    reset_request_id,
    set_request_id,
)


def test_response_carries_generated_request_id(client_no_imd):
    response = client_no_imd.get("/api/v1/health")
    request_id = response.headers.get("x-request-id")
    assert request_id
    assert len(request_id) >= 16


def test_incoming_request_id_is_echoed(client_no_imd):
    response = client_no_imd.get("/api/v1/health", headers={"X-Request-ID": "demo-trace-123"})
    assert response.headers["x-request-id"] == "demo-trace-123"


def test_request_id_is_bound_to_context():
    token = set_request_id("ctx-1")
    try:
        assert get_request_id() == "ctx-1"
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
        payload = json.loads(JsonFormatter().format(record))
        assert payload["request_id"] == "ctx-1"
        assert payload["event"] == "hello"
    finally:
        reset_request_id(token)
    assert get_request_id() is None


def test_extra_fields_are_merged_into_json():
    logger = logging.getLogger("test.extra")
    record = logging.LogRecord("test.extra", logging.INFO, __file__, 1, "evt", None, None)
    record.extra_fields = {"path": "/api/v1/chat", "status": 200}
    payload = json.loads(JsonFormatter().format(record))
    assert payload["path"] == "/api/v1/chat"
    assert payload["status"] == 200


def test_log_event_attaches_fields(caplog):
    logger = logging.getLogger("test.log_event")
    with caplog.at_level(logging.INFO, logger="test.log_event"):
        log_event(logger, "request", method="GET", status=200)
    assert len(caplog.records) == 1
    assert caplog.records[0].extra_fields == {"method": "GET", "status": 200}
