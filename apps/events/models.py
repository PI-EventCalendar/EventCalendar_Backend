from django.conf import settings
from django.db import models

class Event(models.Model):
    """
    Modelo de Evento 
    """
    #relacion fk con el usuario 
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="organizador",
    )
    title = models.CharField("título", max_length=200)
    
    #  Para cumplir con US-01
    course = models.CharField("curso", max_length=150, blank=True, null=True)
    
    #TIPO
    activity_type = models.CharField("tipo de actividad", max_length=100, blank=True, null=True)
    
    description = models.TextField("descripción", blank=True)
    
    # fecha límite de entrega
    event_date = models.DateField("fecha límite de entrega") 
    
    created_at = models.DateTimeField("creado el", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "Actividad"
        verbose_name_plural = "Actividades"
        ordering = ["event_date", "-created_at"] #ORDEN Ordenarlas por fecha de creación: más recientes primeroordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.event_date})"