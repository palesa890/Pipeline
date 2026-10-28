import logging

from django.db.models.deletion import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as default_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    if isinstance(exc, (ProtectedError, RestrictedError)):
        return Response(
            {
                "error": {
                    "code": "resource_in_use",
                    "message": (
                        "The resource cannot be deleted because it is referenced by "
                        "other records."
                    ),
                    "details": {"detail": "The resource is referenced by existing records."},
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    response = default_exception_handler(exc, context)
    if response is None:
        return None

    if response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
        request = context.get("request")
        logger.warning(
            "api_access_denied",
            extra={
                "event_type": "api_access_denied",
                "status_code": response.status_code,
                "path": request.path if request else None,
                "method": request.method if request else None,
            },
        )

    details = response.data
    if isinstance(details, dict) and "detail" in details and len(details) == 1:
        message = str(details["detail"])
    elif response.status_code == 400:
        message = "Request validation failed."
    else:
        message = "The request could not be completed."

    response.data = {
        "error": {
            "code": str(getattr(exc, "default_code", "error")),
            "message": message,
            "details": details,
        }
    }
    return response
