from .models import Event

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