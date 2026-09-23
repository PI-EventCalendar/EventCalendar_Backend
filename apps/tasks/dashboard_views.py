from datetime import datetime
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

        dashboard_data = TaskService.get_daily_dashboard(
            user=request.user, target_date=target_date
        )
        serializer = DailyDashboardSerializer(dashboard_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
