from django.conf import settings
from django.db import models


class TaskCategory(models.Model):
    """
    Categoría para clasificar las tareas logísticas.
    El nombre es único por usuario.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_categories",
        verbose_name="usuario",
    )
    name = models.CharField("nombre de categoría", max_length=100)
    created_at = models.DateTimeField("creado el", auto_now_add=True)

    class Meta:
        verbose_name = "Categoría de Tarea"
        verbose_name_plural = "Categorías de Tareas"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_task_category",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.user.username})"

#SUBTAREAS
class LogisticTask(models.Model):
    """
    Tarea logística asociada a un evento.
    Permite asociar proveedor, horas estimadas, fecha de programación y estado.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        IN_PROGRESS = 'in_progress', 'En Progreso'
        COMPLETADA = 'completed', 'Completada'  # o 'completed'
        CANCELLED = 'cancelled', 'Cancelada'
        

    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="evento",
    )
    category = models.ForeignKey(
        TaskCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
        verbose_name="categoría",
    )
    title = models.CharField("título de la tarea", max_length=200)
    description = models.TextField("descripción", blank=True)
    provider_name = models.CharField("nombre del proveedor", max_length=150, blank=True)
    provider_company = models.CharField(
        "empresa del proveedor", max_length=150, blank=True
    )
    scheduled_date = models.DateField("fecha programada")
    estimated_hours = models.DecimalField(
        "horas estimadas", max_digits=4, decimal_places=2
    )
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    notes = models.TextField("notas adicionales", blank=True)
    created_at = models.DateTimeField("creado el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "Tarea Logística"
        verbose_name_plural = "Tareas Logísticas"
        ordering = ["scheduled_date", "status", "-created_at"]

    def __str__(self):
        return f"{self.title} - {self.scheduled_date} ({self.status})"


class RescheduleHistory(models.Model):
    """
    Historial de reprogramación de una tarea logística.
    Registra cambios de fecha, horas estimadas, motivo y usuario que ejecutó la acción.
    """

    task = models.ForeignKey(
        LogisticTask,
        on_delete=models.CASCADE,
        related_name="reschedule_history",
        verbose_name="tarea",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reschedule_actions",
        verbose_name="usuario que reprogramó",
    )
    previous_date = models.DateField("fecha anterior")
    new_date = models.DateField("nueva fecha")
    previous_hours = models.DecimalField(
        "horas anteriores", max_digits=4, decimal_places=2
    )
    new_hours = models.DecimalField("nuevas horas", max_digits=4, decimal_places=2)
    reason = models.TextField("motivo de reprogramación")
    created_at = models.DateTimeField("fecha de cambio", auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Reprogramación"
        verbose_name_plural = "Historiales de Reprogramación"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reprogramación #{self.id} de Tarea '{self.task.title}' el {self.created_at.strftime('%Y-%m-%d')}"


    from django.conf import settings
from django.db import models

#SUBTAREAS
