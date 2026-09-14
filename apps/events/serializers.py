from rest_framework import serializers

from .models import Event
from .services import EventService


class EventSerializer(serializers.ModelSerializer):
    """Serializer para modelo Event con métricas de progreso calculadas en memoria."""

    progress_percentage = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "event_date",
            "progress_percentage",
            "total_tasks",
            "completed_tasks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "progress_percentage",
            "total_tasks",
            "completed_tasks",
            "created_at",
            "updated_at",
        ]

    def _get_metrics(self, obj):
        if not hasattr(obj, "_cached_metrics"):
            obj._cached_metrics = EventService.calculate_progress(obj)
        return obj._cached_metrics

    def get_progress_percentage(self, obj) -> float:
        return self._get_metrics(obj)["progress_percentage"]

    def get_total_tasks(self, obj) -> int:
        return self._get_metrics(obj)["total_tasks"]

    def get_completed_tasks(self, obj) -> int:
        return self._get_metrics(obj)["completed_tasks"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
