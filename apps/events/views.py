from rest_framework import permissions, viewsets

from apps.core.permissions import IsOwner
from .models import Event
from .serializers import EventSerializer
from .services import EventService


class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet para listar, crear, consultar, actualizar y eliminar eventos.
    Garantiza aislamiento por usuario e inyección de prefetch anti N+1.
    """
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Event.objects.none()
        return EventService.get_events_for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
