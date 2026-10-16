from decimal import Decimal

from rest_framework import serializers

from apps.events.models import Event

from .models import LogisticTask, RescheduleHistory, TaskCategory
from .services import MAX_TASK_HOURS, MIN_TASK_HOURS, TaskService


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
    event_course = serializers.CharField(
        source="event.course", read_only=True, default=""
    )
    event_date = serializers.DateField(source="event.event_date", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )

    class Meta:
        model = LogisticTask
        fields = [
            "id",
            "event",
            "event_title",
            "event_course",
            "category",
            "category_name",
            "title",
            "event_date",
            "description",
            "provider_name",
            "provider_company",
            "scheduled_date",
            "estimated_hours",
            "status",
            "notes",
            "completion_note",
            "created_at",
            "updated_at",
        ]


class LogisticTaskSerializer(serializers.ModelSerializer):
    """Serializer completo para CRUD de tareas logísticas con validación de sobrecarga diaria."""

    event_title = serializers.CharField(source="event.title", read_only=True)
    event_course = serializers.CharField(
        source="event.course", read_only=True, default=""
    )
    event_date = serializers.DateField(source="event.event_date", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )

    class Meta:
        model = LogisticTask
        fields = [
            "id",
            "event",
            "event_title",
            "event_date",
            "event_course",
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
            "completion_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "event_date", "created_at", "updated_at"]

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

    def validate_completion_note(self, value):
        return value.strip() or None if value is not None else None

    def validate(self, attrs):
        user = self.context["request"].user
        event = attrs.get("event", getattr(self.instance, "event", None))
        scheduled_date = attrs.get(
            "scheduled_date", getattr(self.instance, "scheduled_date", None)
        )
        estimated_hours = attrs.get(
            "estimated_hours", getattr(self.instance, "estimated_hours", None)
        )
        exclude_id = self.instance.id if self.instance else None
        if event and scheduled_date:
            if scheduled_date > event.event_date:
                raise serializers.ValidationError(
                    {
                        "scheduled_date": "La fecha programada no puede ser posterior a la fecha del evento."
                    }
                )

        if scheduled_date and estimated_hours is not None:
            max_date = event.event_date if event else None
            TaskService.validate_daily_overload(
                user=user,
                target_date=scheduled_date,
                additional_hours=Decimal(str(estimated_hours)),
                exclude_task_id=exclude_id,
                max_date=max_date,
            )

        return attrs


class RescheduleTaskSerializer(serializers.Serializer):
    """Serializer para la acción de reprogramación de una tarea."""

    new_date = serializers.DateField(required=True)
    new_hours = serializers.DecimalField(max_digits=4, decimal_places=2, required=True)
    reason = serializers.CharField(required=True, min_length=5)


class PostponeTaskSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=10000)


class RescheduleHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RescheduleHistory
        fields = [
            "id",
            "task",
            "user",
            "previous_date",
            "new_date",
            "previous_hours",
            "new_hours",
            "reason",
            "created_at",
        ]
        read_only_fields = ["id", "task", "user", "created_at"]


class DailyDashboardSerializer(serializers.Serializer):
    """Serializer para la respuesta del dashboard 'Hoy'."""

    date = serializers.DateField()
    daily_hour_limit = serializers.DecimalField(max_digits=4, decimal_places=2)
    total_hours_scheduled = serializers.DecimalField(max_digits=4, decimal_places=2)
    capacity_remaining = serializers.DecimalField(max_digits=4, decimal_places=2)
    is_overloaded = serializers.BooleanField()
    tasks = LogisticTaskListSerializer(many=True)
    suggested_dates = serializers.ListField(
        child=serializers.CharField(), required=False
    )
