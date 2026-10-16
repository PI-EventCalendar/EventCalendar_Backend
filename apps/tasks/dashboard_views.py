from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import DailyDashboardSerializer
from .services import TaskService


class TodayTasksView(APIView):
    """
    Endpoint para el dashboard de "Hoy".
    Retorna la lista de tareas del día de hoy (con event y category select_related)
    junto con el cálculo de carga diaria y estado de sobrecarga.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        dashboard_data = TaskService.get_daily_dashboard(
            user=request.user, target_date=today
        )
        serializer = DailyDashboardSerializer(dashboard_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DailyLoadView(APIView):
    """
    Endpoint para consultar la carga diaria de cualquier fecha específica.
    Query param opcional: ?date=YYYY-MM-DD (por defecto hoy).
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("date", OpenApiTypes.DATE, description="Fecha a consultar."),
            OpenApiParameter("exclude_task_id", OpenApiTypes.INT, description="Subtarea propia que se excluye del cálculo."),
            OpenApiParameter("exclude_event_id", OpenApiTypes.INT, description="Evento propio que se excluye del cálculo."),
            OpenApiParameter("suggested_hours", OpenApiTypes.DECIMAL, description="Horas para calcular las fechas futuras elegibles."),
            OpenApiParameter("max_date", OpenApiTypes.DATE, description="Última fecha permitida para las sugerencias."),
            OpenApiParameter("planned_loads", OpenApiTypes.STR, description="JSON de horas ya propuestas por fecha, usado al editar un plan."),
        ],
        responses=DailyDashboardSerializer,
        tags=["Dashboard"],
    )
    def get(self, request, *args, **kwargs):
        date_str = request.query_params.get("date")
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {
                        "error": "Formato de fecha inválido. Utiliza el formato YYYY-MM-DD."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target_date = timezone.localdate()

        try:
            exclude_task_id = self._optional_positive_int(
                request.query_params.get("exclude_task_id"), "exclude_task_id"
            )
            exclude_event_id = self._optional_positive_int(
                request.query_params.get("exclude_event_id"), "exclude_event_id"
            )
            suggested_hours = self._optional_hours(
                request.query_params.get("suggested_hours")
            )
            max_date_str = request.query_params.get("max_date")
            max_date = (
                datetime.strptime(max_date_str, "%Y-%m-%d").date()
                if max_date_str
                else None
            )
            planned_loads = self._planned_loads(request.query_params.get("planned_loads"))
        except (ValueError, InvalidOperation):
            return Response(
                {"error": "Los parámetros de capacidad diaria no son válidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if max_date is not None and max_date < target_date:
            return Response(
                {"error": "max_date no puede ser anterior a date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dashboard_data = TaskService.get_daily_dashboard(
            user=request.user,
            target_date=target_date,
            exclude_task_id=exclude_task_id,
            exclude_event_id=exclude_event_id,
            suggested_hours=suggested_hours,
            max_date=max_date,
            planned_loads=planned_loads,
        )
        serializer = DailyDashboardSerializer(dashboard_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def _optional_positive_int(value, name):
        if value is None:
            return None
        parsed = int(value)
        if parsed < 1:
            raise ValueError(name)
        return parsed

    @staticmethod
    def _optional_hours(value):
        if value is None:
            return None
        parsed = Decimal(value)
        if not parsed.is_finite() or parsed <= 0:
            raise InvalidOperation
        return parsed

    @staticmethod
    def _planned_loads(value):
        if value is None:
            return None
        parsed = json.loads(value)
        if not isinstance(parsed, dict) or len(parsed) > 366:
            raise ValueError("planned_loads")
        result = {}
        for date_str, hours in parsed.items():
            datetime.strptime(date_str, "%Y-%m-%d")
            amount = Decimal(str(hours))
            if not amount.is_finite() or amount < 0:
                raise ValueError("planned_loads")
            result[date_str] = amount
        return result
