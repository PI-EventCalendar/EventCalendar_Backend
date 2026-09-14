from django.conf import settings
from django.db import models


class Event(models.Model):
    """
    Modelo de Evento. Cada evento pertenece a un único usuario (organizador).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="organizador",
    )
    title = models.CharField("título", max_length=200)
    description = models.TextField("descripción", blank=True)
    event_date = models.DateField("fecha del evento")
    created_at = models.DateTimeField("creado el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        ordering = ["event_date", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.event_date})"
