from rest_framework.views import exception_handler as default_exception_handler


def custom_exception_handler(exc, context):
    response = default_exception_handler(exc, context)
    if response is None:
        return None

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
