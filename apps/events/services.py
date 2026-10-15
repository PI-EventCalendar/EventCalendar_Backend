from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.tasks.models import LogisticTask

from .models import Event

# Estados de subtarea que NO impiden finalizar el evento.
CLOSING_TASK_STATUSES = (
    LogisticTask.Status.COMPLETED,
    LogisticTask.Status.CANCELLED,
)


class EventService:
    """
    Servicio de lógica de negocio para la gestión de eventos.
    Implementa optimización anti N+1 con prefetch_related('tasks').
    """

    @staticmethod
    def get_events_for_user(user):
        """
        Obtiene el queryset de eventos de un usuario con 'tasks' prefetched
        para garantizar O(1) queries adicionales en el cálculo del progreso.
        """
        return Event.objects.filter(user=user).prefetch_related("tasks")

    @staticmethod
    def calculate_progress(event: Event) -> dict:
        """
        Calcula el porcentaje de progreso del evento a partir de sus tareas prefetched.
        Evita consultas adicionales a la base de datos iterando sobre la colección en memoria.
        """
        # Se accede a event.tasks.all() utilizando el prefetch cache existente
        tasks = list(event.tasks.all())
        total_tasks = len(tasks)

        # CORRECCIÓN: "completed" debe ir en minúsculas para coincidir exactamente
        # con el valor del TextChoices en el modelo LogisticTask.
        completed_tasks = sum(1 for task in tasks if task.status == "completed")

        progress_percentage = (
            round((completed_tasks / total_tasks) * 100, 2) if total_tasks > 0 else 0.0
        )

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "progress_percentage": progress_percentage,
        }

    @staticmethod
    def get_blocking_tasks(event: Event) -> list:
        """
        Subtareas que impiden finalizar el evento: todas las que no estén
        completadas ni canceladas (pendientes, en progreso o pospuestas).
        """
        return [
            task
            for task in event.tasks.all()
            if task.status not in CLOSING_TASK_STATUSES
        ]

    @classmethod
    @transaction.atomic
    def complete_event(cls, event: Event) -> Event:
        """
        Finaliza el evento solo si todas sus subtareas están completadas
        o canceladas. Si no, lanza un ValidationError (HTTP 400).
        """
        if event.status == Event.Status.COMPLETED:
            return event  # ya estaba finalizado

        blocking_tasks = cls.get_blocking_tasks(event)

        if blocking_tasks:
            count = len(blocking_tasks)
            missing = (
                "Falta 1 subtarea por completar."
                if count == 1
                else f"Faltan {count} subtareas por completar."
            )
            raise ValidationError(
                {
                    "status": (
                        "No puedes finalizar el evento hasta completar "
                        f"todas sus subtareas. {missing}"
                    )
                }
            )

        event.status = Event.Status.COMPLETED
        event.save(update_fields=["status", "updated_at"])
        return event
