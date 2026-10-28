import json
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4

request_id_context = ContextVar("request_id", default="-")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", "")
        if not REQUEST_ID_PATTERN.fullmatch(request_id):
            request_id = str(uuid4())

        token = request_id_context.set(request_id)
        request.META["HTTP_X_REQUEST_ID"] = request_id
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            request_id_context.reset(token)


class JSONFormatter(logging.Formatter):
    def format(self, record):
        request_id = request_id_context.get()
        if request_id == "-":
            request = getattr(record, "request", None)
            request_id = getattr(request, "META", {}).get("HTTP_X_REQUEST_ID", request_id)

        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id,
        }

        standard_fields = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_fields and not key.startswith("_")
        }
        if extra_fields:
            payload["fields"] = extra_fields
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))
