from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import DailyOverloadConflict

from .models import LogisticTask, RescheduleHistory

# Constantes de configuración de límites de horas
DEFAULT_DAILY_HOUR_LIMIT: Decimal = getattr(
    settings, "DEFAULT_DAILY_HOUR_LIMIT", Decimal("6.00")
)
MIN_TASK_HOURS: Decimal = getattr(settings, "MIN_TASK_HOURS", Decimal("0.25"))
MAX_TASK_HOURS: Decimal = getattr(settings, "MAX_TASK_HOURS", Decimal("24.00"))


class TaskService:
    """
    Servicio de lógica de negocio para tareas logísticas y dashboard.
    Implementa prevención N+1 vía select_related('event', 'category')
    y validación estricta de la regla de sobrecarga diaria (> user.daily_hour_limit).
    """

    DEFAULT_DAILY_HOUR_LIMIT = DEFAULT_DAILY_HOUR_LIMIT
    MIN_TASK_HOURS = MIN_TASK_HOURS
    MAX_TASK_HOURS = MAX_TASK_HOURS
    CAPACITY_STATUSES = (
        LogisticTask.Status.PENDING,
        LogisticTask.Status.IN_PROGRESS,
        LogisticTask.Status.POSTPONED,
    )

    @classmethod
    def get_daily_hour_limit(cls, user) -> Decimal:
        configured = getattr(user, "daily_hour_limit", None)
        try:
            limit = cls.DEFAULT_DAILY_HOUR_LIMIT if configured is None else Decimal(str(configured))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({"daily_hour_limit": "La capacidad diaria configurada no es válida."})
        if not limit.is_finite() or not Decimal("1") <= limit <= Decimal("16"):
            raise ValidationError({"daily_hour_limit": "La capacidad diaria configurada no es válida."})
        return limit

    @staticmethod
    def get_today_tasks(user, target_date=None):
        """
        Obtiene las tareas programadas para la fecha indicada (por defecto hoy)
        utilizando select_related('event', 'category') para eliminar consultas N+1.
        """
        if target_date is None:
            target_date = timezone.localdate()

        return LogisticTask.objects.filter(
            event__user=user,
            scheduled_date=target_date,
        ).select_related("event", "category")

    @staticmethod
    def get_daily_scheduled_hours(
        user, target_date, exclude_task_id=None, exclude_event_id=None
    ) -> Decimal:
        """
        Calcula la suma de horas programadas por un usuario para una fecha determinada.
        Permite excluir una tarea (útil en actualizaciones o reprogramaciones).
        """
        queryset = LogisticTask.objects.filter(
            event__user=user,
            scheduled_date=target_date,
            status__in=TaskService.CAPACITY_STATUSES,
        )
        if exclude_task_id:
            queryset = queryset.exclude(id=exclude_task_id)
        if exclude_event_id:
            queryset = queryset.exclude(event_id=exclude_event_id)

        aggregate_result = queryset.aggregate(total_hours=Sum("estimated_hours"))
        total = aggregate_result["total_hours"]
        return Decimal(str(total)) if total is not None else Decimal("0.00")

    @classmethod
    def get_overloaded_dates(cls, user, daily_limit: Decimal) -> list[dict]:
        """Return open-task dates that would exceed a proposed daily limit."""
        rows = (
            LogisticTask.objects.filter(
                event__user=user,
                status__in=cls.CAPACITY_STATUSES,
            )
            .values("scheduled_date")
            .annotate(total_hours=Sum("estimated_hours"))
            .order_by("scheduled_date")
        )
        return [
            {
                "date": row["scheduled_date"].isoformat(),
                "hours": str(row["total_hours"]),
                "tasks": list(
                    LogisticTask.objects.filter(
                        event__user=user,
                        scheduled_date=row["scheduled_date"],
                        status__in=cls.CAPACITY_STATUSES,
                    )
                    .select_related("event")
                    .values("id", "title", "event__title", "estimated_hours")
                    .order_by("id")
                ),
            }
            for row in rows
            if Decimal(str(row["total_hours"])) > daily_limit
        ]

    @classmethod
    def validate_daily_limit_change(cls, user, daily_limit: Decimal) -> None:
        conflicts = cls.get_overloaded_dates(user, daily_limit)
        if conflicts:
            raise DailyOverloadConflict(
                detail={
                    "error": "DailyOverloadConflict",
                    "detail": "El nuevo límite dejaría subtareas por encima de la capacidad diaria.",
                    "daily_hour_limit": str(daily_limit),
                    "conflicts": conflicts,
                }
            )

    @classmethod
    def get_suggested_dates(
        cls,
        user,
        target_date,
        hours: Decimal,
        days_ahead: int = 30,
        exclude_task_id=None,
        exclude_event_id=None,
        max_date=None,
        planned_loads=None,
    ) -> list[str]:
        """
        Calcula fechas alternativas a partir de target_date en las que el usuario
        cuenta con capacidad disponible suficiente para programar 'hours'.
        Retorna una lista de cadenas en formato YYYY-MM-DD (máximo 3 sugerencias).
        Si se especifica max_date, ninguna fecha sugerida superará dicho límite.
        """
        suggestions = []
        daily_limit = cls.get_daily_hour_limit(user)
        # Buscar después de la fecha en conflicto; nunca se propone hoy.
        first_future_date = max(target_date, timezone.localdate()) + timedelta(days=1)
        for i in range(days_ahead):
            candidate_date = first_future_date + timedelta(days=i)
            if max_date and candidate_date > max_date:
                break
            current_hours = cls.get_daily_scheduled_hours(
                user,
                candidate_date,
                exclude_task_id=exclude_task_id,
                exclude_event_id=exclude_event_id,
            )
            current_hours += Decimal(str((planned_loads or {}).get(candidate_date.isoformat(), 0)))
            if current_hours + Decimal(str(hours)) <= daily_limit:
                suggestions.append(candidate_date.isoformat())
                if len(suggestions) >= 3:
                    break
        return suggestions

    @classmethod
    def validate_task_plan(cls, user, tasks, replace_event_id=None, max_date=None):
        """Validate a complete plan against the user's global daily workload."""
        totals = {}
        existing_totals = {}
        existing = LogisticTask.objects.filter(
            event__user=user,
            status__in=cls.CAPACITY_STATUSES,
        )
        if replace_event_id is not None:
            existing = existing.exclude(event_id=replace_event_id)

        for date, hours in existing.values_list("scheduled_date").annotate(
            total=Sum("estimated_hours")
        ):
            existing_totals[date] = Decimal(str(hours))
            totals[date] = existing_totals[date]

        proposed_totals = {}
        for task in tasks:
            status = task.get("status", LogisticTask.Status.PENDING)
            if status in (
                LogisticTask.Status.COMPLETED,
                LogisticTask.Status.CANCELLED,
            ):
                continue
            date = task.get("scheduled_date")
            if date is not None:
                hours = Decimal(str(task.get("estimated_hours", 0)))
                proposed_totals[date] = (
                    proposed_totals.get(date, Decimal("0.00")) + hours
                )
                totals[date] = totals.get(date, Decimal("0.00")) + hours

        daily_limit = cls.get_daily_hour_limit(user)

        for date, hours in totals.items():
            if hours > daily_limit:
                attempted_hours = proposed_totals.get(date, Decimal("0.00"))
                suggested_dates = cls.get_suggested_dates(
                    user=user,
                    target_date=date,
                    hours=attempted_hours,
                    exclude_event_id=replace_event_id,
                    max_date=max_date,
                    planned_loads=proposed_totals,
                )
                raise DailyOverloadConflict(
                    target_date=date,
                    current_hours=existing_totals.get(date, Decimal("0.00")),
                    attempted_hours=attempted_hours,
                    daily_limit=daily_limit,
                    suggested_dates=suggested_dates,
                )

    @classmethod
    def validate_daily_overload(
        cls,
        user,
        target_date,
        additional_hours: Decimal,
        exclude_task_id=None,
        max_date=None,
    ):
        """
        Verifica si agregar 'additional_hours' a la fecha 'target_date' excede el límite
        diario permitido para el usuario (user.daily_hour_limit).
        Si se sobrepasa, lanza una excepción DailyOverloadConflict (HTTP 409).
        """
        current_hours = cls.get_daily_scheduled_hours(
            user, target_date, exclude_task_id=exclude_task_id
        )
        additional_decimal = Decimal(str(additional_hours))
        projected_hours = current_hours + additional_decimal
        daily_limit = cls.get_daily_hour_limit(user)

        if projected_hours > daily_limit:
            suggested_dates = cls.get_suggested_dates(
                user=user,
                target_date=target_date,
                hours=additional_decimal,
                exclude_task_id=exclude_task_id,
                max_date=max_date,
            )
            raise DailyOverloadConflict(
                target_date=target_date,
                current_hours=current_hours,
                attempted_hours=additional_decimal,
                daily_limit=daily_limit,
                suggested_dates=suggested_dates,
            )

    @classmethod
    def get_daily_dashboard(
        cls,
        user,
        target_date=None,
        exclude_task_id=None,
        exclude_event_id=None,
        suggested_hours=None,
        max_date=None,
        planned_loads=None,
    ) -> dict:
        """
        Genera el resumen de carga diaria para el dashboard del usuario.
        """
        if target_date is None:
            target_date = timezone.localdate()

        tasks_qs = cls.get_today_tasks(user, target_date)
        if exclude_task_id:
            tasks_qs = tasks_qs.exclude(id=exclude_task_id)
        if exclude_event_id:
            tasks_qs = tasks_qs.exclude(event_id=exclude_event_id)
        total_hours = cls.get_daily_scheduled_hours(
            user,
            target_date,
            exclude_task_id=exclude_task_id,
            exclude_event_id=exclude_event_id,
        )
        daily_limit = cls.get_daily_hour_limit(user)
        capacity_remaining = max(Decimal("0.00"), daily_limit - total_hours)
        is_overloaded = total_hours > daily_limit

        result = {
            "date": target_date,
            "daily_hour_limit": daily_limit,
            "total_hours_scheduled": total_hours,
            "capacity_remaining": capacity_remaining,
            "is_overloaded": is_overloaded,
            "tasks": tasks_qs,
        }
        if suggested_hours is not None:
            result["suggested_dates"] = cls.get_suggested_dates(
                user=user,
                target_date=target_date,
                hours=suggested_hours,
                exclude_task_id=exclude_task_id,
                exclude_event_id=exclude_event_id,
                max_date=max_date,
                planned_loads=planned_loads,
            )
        return result

    @classmethod
    def postpone_task(cls, task: LogisticTask, user, note="") -> LogisticTask:
        """Move a postponed task to the nearest future date with available capacity."""
        today = timezone.localdate()

        with transaction.atomic():
            # Locking the organizer serializes concurrent postpone operations for that user.
            locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
            locked_task = LogisticTask.objects.select_for_update().select_related("event").get(
                pk=task.pk, event__user_id=locked_user.pk
            )
            if locked_task.status in (LogisticTask.Status.COMPLETED, LogisticTask.Status.CANCELLED):
                raise ValidationError({"status": "No se puede posponer una subtarea completada o cancelada."})

            hours = Decimal(str(locked_task.estimated_hours))
            if not hours.is_finite() or hours <= 0 or hours > cls.MAX_TASK_HOURS:
                raise ValidationError({"estimated_hours": "Las horas estimadas de la subtarea no son válidas."})

            start_date = max(today + timedelta(days=1), locked_task.scheduled_date + timedelta(days=1))

            max_date = locked_task.event.event_date if locked_task.event_id else start_date + timedelta(days=364)
            end_date = min(max_date, start_date + timedelta(days=364))

            daily_limit = cls.get_daily_hour_limit(locked_user)

            new_date = None
            for offset in range(max(0, (end_date - start_date).days + 1)):
                candidate = start_date + timedelta(days=offset)
                current_hours = cls.get_daily_scheduled_hours(
                    locked_user, candidate, exclude_task_id=locked_task.id
                )
                if current_hours + hours <= daily_limit:
                    new_date = candidate
                    break

            if new_date is None:
                raise DailyOverloadConflict(
                    detail={
                        "error": "NoAvailableDate",
                        "detail": "No se encontró una fecha futura con capacidad diaria suficiente.",
                        "daily_hour_limit": str(daily_limit),
                        "attempted_hours": str(hours),
                    }
                )

            previous_date = locked_task.scheduled_date
            if previous_date != new_date:
                RescheduleHistory.objects.create(
                    task=locked_task,
                    user=locked_user,
                    previous_date=previous_date,
                    new_date=new_date,
                    previous_hours=locked_task.estimated_hours,
                    new_hours=locked_task.estimated_hours,
                    reason="Posposición automática",
                )
            locked_task.scheduled_date = new_date
            locked_task.status = LogisticTask.Status.POSTPONED
            locked_task.notes = (note or "").strip()
            locked_task.save(update_fields=["scheduled_date", "status", "notes", "updated_at"])

        return locked_task

    @classmethod
    def reschedule_task(
        cls, task: LogisticTask, user, new_date, new_hours: Decimal, reason: str
    ) -> LogisticTask:
        """
        Reprograma una tarea logística, validando la regla de sobrecarga para la nueva fecha,
        generando la auditoría en RescheduleHistory y actualizando la tarea en una transacción atómica.
        """
        new_hours_decimal = Decimal(str(new_hours))
        with transaction.atomic():
            locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
            locked_task = LogisticTask.objects.select_for_update().select_related("event").get(
                pk=task.pk, event__user_id=locked_user.pk
            )
            if locked_task.event and new_date > locked_task.event.event_date:
                raise ValidationError(
                    {"new_date": "La fecha reprogramada no puede ser posterior a la fecha del evento."}
                )
            cls.validate_daily_overload(
                user=locked_user,
                target_date=new_date,
                additional_hours=new_hours_decimal,
                exclude_task_id=locked_task.id,
                max_date=locked_task.event.event_date if locked_task.event else None,
            )
            RescheduleHistory.objects.create(
                task=locked_task,
                user=locked_user,
                previous_date=locked_task.scheduled_date,
                new_date=new_date,
                previous_hours=locked_task.estimated_hours,
                new_hours=new_hours_decimal,
                reason=reason,
            )

            locked_task.scheduled_date = new_date
            locked_task.estimated_hours = new_hours_decimal
            if locked_task.status == LogisticTask.Status.POSTPONED:
                locked_task.status = LogisticTask.Status.PENDING
            locked_task.save(
                update_fields=[
                    "scheduled_date",
                    "estimated_hours",
                    "status",
                    "updated_at",
                ]
            )

        return locked_task
