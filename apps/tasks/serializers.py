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


class RescheduleHistorySerializer(serializers.ModelSerializer):
    new_date = serializers.DateField(required=False)
    scheduled_date = serializers.DateField(required=False)
    new_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        required=False,
        min_value=MIN_TASK_HOURS,
        max_value=MAX_TASK_HOURS,
    )
    estimated_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        required=False,
        min_value=MIN_TASK_HOURS,
        max_value=MAX_TASK_HOURS,
    )
    reason = serializers.CharField(required=False, default="Reprogramación de tarea")

    def validate(self, attrs):
        task = self.context.get("task")
        new_date = attrs.get("new_date") or attrs.get("scheduled_date")
        if not new_date:
            raise serializers.ValidationError(
                {"new_date": "La nueva fecha es requerida."}
            )
        attrs["new_date"] = new_date

        if task and hasattr(task, "event") and task.event:
            if new_date > task.event.event_date:
                err_key = (
                    "scheduled_date"
                    if ("scheduled_date" in attrs and "new_date" not in attrs)
                    else "new_date"
                )
                raise serializers.ValidationError(
                    {
                        err_key: "La fecha reprogramada no puede ser posterior a la fecha del evento."
                    }
                )

        new_hours = attrs.get("new_hours")
        if new_hours is None:
            new_hours = attrs.get("estimated_hours")
        if new_hours is None and task:
            new_hours = task.estimated_hours
        elif new_hours is None:
            raise serializers.ValidationError(
                {"new_hours": "Las horas estimadas son requeridas."}
            )
        attrs["new_hours"] = new_hours

        reason = attrs.get("reason")
        if not reason or not str(reason).strip():
            attrs["reason"] = "Reprogramación de tarea"

        return attrs


class DailyDashboardSerializer(serializers.Serializer):
    """Serializer para la respuesta del dashboard 'Hoy'."""

    date = serializers.DateField()
    daily_hour_limit = serializers.DecimalField(max_digits=4, decimal_places=2)
    total_hours_scheduled = serializers.DecimalField(max_digits=4, decimal_places=2)
    capacity_remaining = serializers.DecimalField(max_digits=4, decimal_places=2)
    is_overloaded = serializers.BooleanField()
    tasks = LogisticTaskListSerializer(many=True)
