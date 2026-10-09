from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsOwner

from .models import LogisticTask, TaskCategory
from .serializers import (
    LogisticTaskListSerializer,
    LogisticTaskSerializer,
    RescheduleHistorySerializer,
    RescheduleTaskSerializer,
    TaskCategorySerializer,
)
from .services import TaskService

# @extend_schema(tags=["Tasks"])


class TaskCategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD para categorías de tareas pertenecientes al usuario autenticado.
    """

    serializer_class = TaskCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TaskCategory.objects.none()
        return TaskCategory.objects.filter(user=self.request.user)


class LogisticTaskViewSet(viewsets.ModelViewSet):
    """
    CRUD para tareas logísticas con endpoints adicionales para reprogramar y consultar historial.
    Asegura optimización con select_related y permisos por usuario.
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return LogisticTaskListSerializer
        return LogisticTaskSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LogisticTask.objects.none()
        queryset = LogisticTask.objects.filter(
            event__user=self.request.user
        ).select_related("event", "category")

        # Filtro opcional por evento
        event_id = self.request.query_params.get("event")
        if event_id:
            queryset = queryset.filter(event_id=event_id)

        # Filtro opcional por fecha
        date_filter = self.request.query_params.get("date")
        if date_filter:
            queryset = queryset.filter(scheduled_date=date_filter)

        return queryset

    @action(detail=True, methods=["post"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        """
        Reprograma la fecha y horas estimadas de la tarea, auditando el cambio en RescheduleHistory.
        Si la nueva fecha excede el límite diario del usuario, retorna HTTP 409 Conflict.
        """
        task = self.get_object()
        serializer = RescheduleTaskSerializer(
            data=request.data, context={"task": task, "request": request}
        )
        serializer.is_valid(raise_exception=True)

        updated_task = TaskService.reschedule_task(
            task=task,
            user=request.user,
            new_date=serializer.validated_data["new_date"],
            new_hours=serializer.validated_data["new_hours"],
            reason=serializer.validated_data["reason"],
        )

        return Response(
            LogisticTaskListSerializer(updated_task).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        Consulta el historial de reprogramaciones de una tarea específica.
        """
        task = self.get_object()
        history_qs = task.reschedule_history.all().select_related("user")
        serializer = RescheduleHistorySerializer(history_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Consultar tareas de Hoy",
        description=(
            "Obtiene las subtareas del usuario autenticado que aún no han sido "
            "completadas. Permite filtrar opcionalmente por evento y estado."
        ),
        parameters=[
            OpenApiParameter(
                name="event",
                description="ID del evento al que pertenecen las subtareas.",
                required=False,
                type=OpenApiTypes.INT,
            ),
            OpenApiParameter(
                name="status",
                description="Estado de la subtarea.",
                required=False,
                type=OpenApiTypes.STR,
                enum=[
                    "pending",
                    "in_progress",
                    "completed",
                    "cancelled",
                ],
            ),
        ],
        responses=LogisticTaskListSerializer(many=True),
        tags=["Hoy"],
    )
    # Este crea la ruta (como las tareas ya estaban en ligistictask la pagina hoy solo consumia.)

    @action(detail=False, methods=["get"], url_path="hoy")
    def hoy(self, request):
        """
        Consulta las subtareas pendientes del usuario para la vista Hoy.

        Permite filtrar por:
        - evento
        - estado

        Utiliza la misma paginación global configurada
        para el resto de los endpoints.
        """

        queryset = self.get_queryset()

        # La vista Hoy no muestra tareas completadas
        queryset = queryset.exclude(status="completed")

        # Filtro por estado
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Utilizar la paginación global de DRF
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = LogisticTaskListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Fallback por seguridad si la paginación estuviera deshabilitada
        serializer = LogisticTaskListSerializer(queryset, many=True)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
