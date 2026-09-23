from decimal import Decimal
from rest_framework import serializers

from apps.events.models import Event
from .models import LogisticTask, RescheduleHistory, TaskCategory
from .services import TaskService


class TaskCategorySerializer(serializers.ModelSerializer):
    """Serializer para categorías de tareas logísticas."""

    class Meta:
        model = TaskCategory
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class LogisticTaskListSerializer(serializers.ModelSerializer):
    """Serializer optimizado para listado y dashboard de tareas logísticas."""

    event_title = serializers.CharField(source="event.title", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )

    class Meta:
        model = LogisticTask
        fields = [
            "id",
            "event",
            "event_title",
            "category",
            "category_name",
            "title",
            "description",
            "provider_name",
            "provider_company",
            "scheduled_date",
            "estimated_hours",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]


class LogisticTaskSerializer(serializers.ModelSerializer):
    """Serializer completo para CRUD de tareas logísticas con validación de sobrecarga diaria."""

    event_title = serializers.CharField(source="event.title", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )

    class Meta:
        model = LogisticTask
        fields = [
            "id",
            "event",
            "event_title",
            "category",
            "category_name",
            "title",
            "description",
            "provider_name",
            "provider_company",
            "scheduled_date",
            "estimated_hours",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_event(self, value):
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError(
                "No tienes permiso para asignar tareas a este evento."
            )
        return value

    def validate_category(self, value):
        if value is None:
            return value
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError(
                "No tienes permiso para utilizar esta categoría."
            )
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        scheduled_date = attrs.get(
            "scheduled_date", getattr(self.instance, "scheduled_date", None)
        )
        estimated_hours = attrs.get(
            "estimated_hours", getattr(self.instance, "estimated_hours", None)
        )
        exclude_id = self.instance.id if self.instance else None

        if scheduled_date and estimated_hours is not None:
            TaskService.validate_daily_overload(
                user=user,
                target_date=scheduled_date,
                additional_hours=Decimal(str(estimated_hours)),
                exclude_task_id=exclude_id,
            )

        return attrs


class RescheduleTaskSerializer(serializers.Serializer):
    """Serializer para la acción de reprogramación de una tarea."""

    new_date = serializers.DateField(required=True)
    new_hours = serializers.DecimalField(max_digits=4, decimal_places=2, required=True)
    reason = serializers.CharField(required=True, min_length=5)


class RescheduleHistorySerializer(serializers.ModelSerializer):
    """Serializer para consultar el historial de reprogramaciones de una tarea."""

    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = RescheduleHistory
        fields = [
            "id",
            "task",
            "user",
            "username",
            "previous_date",
            "new_date",
            "previous_hours",
            "new_hours",
            "reason",
            "created_at",
        ]
        read_only_fields = fields


class DailyDashboardSerializer(serializers.Serializer):
    """Serializer para la respuesta del dashboard 'Hoy'."""

    date = serializers.DateField()
    daily_hour_limit = serializers.DecimalField(max_digits=4, decimal_places=2)
    total_hours_scheduled = serializers.DecimalField(max_digits=4, decimal_places=2)
    capacity_remaining = serializers.DecimalField(max_digits=4, decimal_places=2)
    is_overloaded = serializers.BooleanField()
    tasks = LogisticTaskListSerializer(many=True)
