from django.db import OperationalError, InterfaceError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """Hide transient database failures behind a stable, retryable API response."""
    if isinstance(exc, (OperationalError, InterfaceError)):
        return Response(
            {
                "error": "DatabaseUnavailable",
                "detail": "El servicio de datos no está disponible temporalmente. Inténtalo nuevamente.",
            },
            status=503,
        )
    return drf_exception_handler(exc, context)
