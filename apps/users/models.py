from decimal import Decimal
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Modelo de usuario personalizado para EventCalendar.
    Extiende AbstractUser e incorpora un límite diario de horas para tareas logísticas.
    """

    email = models.EmailField("correo electrónico", unique=True)
    daily_hour_limit = models.DecimalField(
        "límite de horas diarias",
        max_digits=4,
        decimal_places=2,
        default=Decimal("6.00"),
        help_text="Límite máximo de horas de trabajo asignables en un solo día.",
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username
