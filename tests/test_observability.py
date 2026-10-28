import json
import logging
from types import SimpleNamespace

from config.observability import JSONFormatter, request_id_context


def test_json_formatter_includes_request_id_and_structured_fields():
    token = request_id_context.set("trace-42")
    try:
        record = logging.LogRecord(
            "apps.core",
            logging.INFO,
            __file__,
            12,
            "reservation_created",
            (),
            None,
        )
        record.event_type = "reservation_created"
        record.reservation_id = 17

        payload = json.loads(JSONFormatter().format(record))
    finally:
        request_id_context.reset(token)

    assert payload["request_id"] == "trace-42"
    assert payload["message"] == "reservation_created"
    assert payload["fields"] == {
        "event_type": "reservation_created",
        "reservation_id": 17,
    }


def test_json_formatter_gets_request_id_from_django_request_after_middleware():
    record = logging.LogRecord(
        "django.request",
        logging.ERROR,
        __file__,
        30,
        "Internal Server Error",
        (),
        None,
    )
    record.request = SimpleNamespace(META={"HTTP_X_REQUEST_ID": "trace-from-request"})

    payload = json.loads(JSONFormatter().format(record))

    assert payload["request_id"] == "trace-from-request"
