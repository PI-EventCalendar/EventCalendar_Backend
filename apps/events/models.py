from django.conf import settings
from django.db import models


class Event(models.Model):
    """
    Modelo de Evento
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        IN_PROGRESS = "in_progress", "En progreso"
        COMPLETED = "completed", "Finalizado"

    # relacion fk con el usuario
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="organizador",
    )
    title = models.CharField("título", max_length=200)

    #  Para cumplir con US-01
    course = models.CharField("curso", max_length=150, blank=True, null=True)

    # TIPO
    activity_type = models.CharField(
        "tipo de actividad", max_length=100, blank=True, null=True
    )

    description = models.TextField("descripción", blank=True)
    location = models.CharField("lugar", max_length=255, blank=True, default="")

    # fecha límite de entrega
    event_date = models.DateField("fecha límite de entrega")

    # Estado del evento. Solo pasa a COMPLETED mediante
    # EventService.complete_event (que valida las subtareas) y vuelve a
    # IN_PROGRESS automáticamente si se reabre alguna subtarea.
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField("creado el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "Actividad"
        verbose_name_plural = "Actividades"
        ordering = [
            "event_date",
            "-created_at",
        ]  # ORDEN Ordenarlas por fecha de creación: más recientes primeroordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.event_date})"

    def reopen_if_completed(self):
        """
        Si el evento estaba finalizado, lo devuelve a "En progreso".

        Se llama cuando una subtarea queda abierta (pendiente, en progreso
        o pospuesta) o se crea una subtarea nueva en un evento finalizado.
        """
        if self.status == self.Status.COMPLETED:
            self.status = self.Status.IN_PROGRESS
            self.save(update_fields=["status", "updated_at"])
