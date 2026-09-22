from rest_framework import permissions, viewsets
from apps.core.permissions import IsOwner
from .models import Event
from .serializers import EventSerializer
from .services import EventService
from drf_spectacular.utils import extend_schema
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