from rest_framework import serializers
from decimal import Decimal
from .models import Event
from .services import EventService

from apps.tasks.models import LogisticTask 


class NestedTaskCreateSerializer(serializers.ModelSerializer):

    """
    Serializador simplificado EXCLUSIVO para recibir tareas
    al momento de crear un Evento.

    Se utiliza cuando un evento y sus subtareas se crean
    mediante una sola petición POST /api/v1/events/.
    """

    # ============================================================
    # VALIDACIÓN DE HORAS ESTIMADAS
    # ============================================================
    
    # ============================================================

    estimated_hours = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    class Meta:
        model = LogisticTask
        fields = [
            'title',
            'scheduled_date',
            'estimated_hours',
            'status'
        ]


class EventSerializer(serializers.ModelSerializer):
    """Serializer para modelo Event con métricas de progreso calculadas en memoria y creación anidada."""

    progress_percentage = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()
    
    #Campo para recibir el array de tareas en el JSON
    tasks = NestedTaskCreateSerializer(many=True, required=False)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "course",          
            "activity_type",   
            "description",
            "event_date",
            "progress_percentage",
            "total_tasks",
            "completed_tasks",
            "tasks",           #CREACION ANIDADA
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

    # --- LÓGICA DE MÉTRICAS (T4) INTACTA ---
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

    # --- LÓGICA DE CREACIÓN FUSIONADA (T1) ---
    def create(self, validated_data):
        # 1. Asignamos el usuario (Tu lógica original)
        validated_data["user"] = self.context["request"].user
        
        # 2. Extraemos las tareas del JSON (Nuestra nueva lógica)
        tasks_data = validated_data.pop('tasks', [])
        
        # 3. Creamos el Evento principal usando super()
        event = super().create(validated_data)
        
        # 4. Creamos cada subtarea asociada al evento
        for task_data in tasks_data:
            LogisticTask.objects.create(event=event, **task_data)
            

        return event

    # NUEVO
    def validate_activity_type(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "El tipo de actividad es obligatorio."
            )

        return value