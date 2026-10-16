from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsOwner

from .models import Event
from .serializers import EventSerializer
from .services import EventService


@extend_schema_view(
    list=extend_schema(responses={503: OpenApiResponse(description="Base de datos temporalmente no disponible.")}),
    retrieve=extend_schema(responses={503: OpenApiResponse(description="Base de datos temporalmente no disponible.")}),
    create=extend_schema(responses={503: OpenApiResponse(description="Base de datos temporalmente no disponible.")}),
    update=extend_schema(responses={503: OpenApiResponse(description="Base de datos temporalmente no disponible.")}),
    partial_update=extend_schema(responses={503: OpenApiResponse(description="Base de datos temporalmente no disponible.")}),
    destroy=extend_schema(responses={503: OpenApiResponse(description="Base de datos temporalmente no disponible.")}),
)
@extend_schema(tags=["Events"])
class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, crear, consultar, actualizar y eliminar eventos.
    Garantiza aislamiento por usuario e inyección de prefetch anti N+1.
    """

    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        """
        Devuelve los eventos del usuario autenticado.
        Usa EventService.get_events_for_user para traer las tareas (prefetch_related('tasks'))
        evitando hacer múltiples consultas a la base de datos (problema N+1).
        """
        if getattr(self, "swagger_fake_view", False):
            return Event.objects.none()
        return EventService.get_events_for_user(self.request.user)

    def perform_create(self, serializer):
        """
        Se ejecuta automáticamente al hacer POST a /api/v1/events/.
        Pasa el 'request' en el contexto y asigna el usuario autenticado.
        El método 'create' del EventSerializer se encarga de guardar
        el Evento y crear sus tareas asociadas (LogisticTask).
        """
        serializer.save(user=self.request.user)

    @extend_schema(request=None, responses=EventSerializer)
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """
        POST /api/v1/events/{id}/complete/

        Finaliza el evento. Responde 400 si quedan subtareas sin completar
        (las canceladas no cuentan).
        """
        event = self.get_object()
        event = EventService.complete_event(event)
        return Response(self.get_serializer(event).data)
