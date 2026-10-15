from datetime import date, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.exceptions import DailyOverloadConflict
from apps.events.models import Event
from apps.tasks.models import LogisticTask, RescheduleHistory, TaskCategory
from apps.tasks.services import TaskService

User = get_user_model()


class TaskServiceOverloadTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="taskplanner",
            email="planner@example.com",
            password="securepassword123",
            daily_hour_limit=Decimal("6.00"),
        )
        self.event = Event.objects.create(
            user=self.user,
            title="Conferencia Anual",
            event_date=date.today() + timedelta(days=10),
        )
        self.category = TaskCategory.objects.create(
            user=self.user,
            name="Sonido y Luces",
        )

    def test_daily_scheduled_hours_calculation(self):
        target_date = date.today()
        LogisticTask.objects.create(
            event=self.event,
            category=self.category,
            title="Montaje de escenario",
            scheduled_date=target_date,
            estimated_hours=Decimal("4.00"),
        )
        hours = TaskService.get_daily_scheduled_hours(self.user, target_date)
        self.assertEqual(hours, Decimal("4.00"))

    def test_overload_throws_409_conflict(self):
        target_date = date.today()
        LogisticTask.objects.create(
            event=self.event,
            category=self.category,
            title="Pruebas de sonido",
            scheduled_date=target_date,
            estimated_hours=Decimal("4.50"),
        )

        # Intentar sumar 2.00 horas más superará el límite de 6.00 (4.50 + 2.00 = 6.50)
        with self.assertRaises(DailyOverloadConflict):
            TaskService.validate_daily_overload(
                user=self.user,
                target_date=target_date,
                additional_hours=Decimal("2.00"),
            )

    def test_postponed_tasks_consume_capacity_on_their_assigned_date(self):
        target_date = date.today() + timedelta(days=1)
        LogisticTask.objects.create(
            event=self.event,
            title="Tarea pospuesta",
            scheduled_date=target_date,
            estimated_hours=Decimal("4.50"),
            status=LogisticTask.Status.POSTPONED,
        )

        with self.assertRaises(DailyOverloadConflict):
            TaskService.validate_daily_overload(
                user=self.user,
                target_date=target_date,
                additional_hours=Decimal("2.00"),
            )

    def test_invalid_capacity_is_not_replaced_by_the_default(self):
        self.user.daily_hour_limit = Decimal("0.00")
        with self.assertRaises(ValidationError):
            TaskService.get_daily_dashboard(self.user, date.today())

    @patch("apps.tasks.services.timezone.localdate", return_value=date(2026, 10, 15))
    def test_postpone_rejects_non_positive_task_hours_without_mutation(self, _localdate):
        task = LogisticTask.objects.create(
            event=self.event,
            title="Duración inválida",
            scheduled_date=date(2026, 10, 15),
            estimated_hours=Decimal("0.00"),
        )
        with self.assertRaises(ValidationError):
            TaskService.postpone_task(task, self.user)
        task.refresh_from_db()
        self.assertEqual(task.scheduled_date, date(2026, 10, 15))
        self.assertEqual(task.status, LogisticTask.Status.PENDING)

    def test_reschedule_task_and_history_creation(self):
        original_date = date.today()
        new_date = date.today() + timedelta(days=2)
        task = LogisticTask.objects.create(
            event=self.event,
            category=self.category,
            title="Instalación de proyectores",
            scheduled_date=original_date,
            estimated_hours=Decimal("3.00"),
        )

        updated_task = TaskService.reschedule_task(
            task=task,
            user=self.user,
            new_date=new_date,
            new_hours=Decimal("2.50"),
            reason="Retraso en el envío de equipos",
        )

        self.assertEqual(updated_task.scheduled_date, new_date)
        self.assertEqual(updated_task.estimated_hours, Decimal("2.50"))
        self.assertEqual(updated_task.status, LogisticTask.Status.PENDING)

        history = RescheduleHistory.objects.filter(task=task).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.previous_date, original_date)
        self.assertEqual(history.new_date, new_date)
        self.assertEqual(history.previous_hours, Decimal("3.00"))
        self.assertEqual(history.new_hours, Decimal("2.50"))
        self.assertEqual(history.reason, "Retraso en el envío de equipos")

    @patch("apps.tasks.services.timezone.localdate")
    def test_postpone_skips_today_and_full_dates_and_persists_history(self, localdate):
        today = date(2026, 10, 15)
        localdate.return_value = today
        self.user.daily_hour_limit = Decimal("5.00")
        self.user.save(update_fields=["daily_hour_limit"])
        task = LogisticTask.objects.create(
            event=self.event,
            title="Tarea a posponer",
            scheduled_date=today,
            estimated_hours=Decimal("2.00"),
        )
        LogisticTask.objects.create(
            event=self.event,
            title="Mañana ocupada",
            scheduled_date=today + timedelta(days=1),
            estimated_hours=Decimal("4.00"),
        )
        LogisticTask.objects.create(
            event=self.event,
            title="Segundo día disponible",
            scheduled_date=today + timedelta(days=2),
            estimated_hours=Decimal("3.00"),
        )

        updated = TaskService.postpone_task(task, self.user, "  Proveedor retrasado  ")

        self.assertEqual(updated.scheduled_date, today + timedelta(days=2))
        self.assertEqual(updated.status, LogisticTask.Status.POSTPONED)
        self.assertEqual(updated.notes, "Proveedor retrasado")
        history = RescheduleHistory.objects.get(task=task)
        self.assertEqual(history.new_date, updated.scheduled_date)
        self.assertEqual(history.reason, "Posposición automática")

    @patch("apps.tasks.services.timezone.localdate", return_value=date(2026, 10, 15))
    def test_postpone_uses_latest_persisted_limit(self, _localdate):
        task = LogisticTask.objects.create(
            event=self.event,
            title="Límite actualizado",
            scheduled_date=date(2026, 10, 15),
            estimated_hours=Decimal("2.00"),
        )
        LogisticTask.objects.create(
            event=self.event,
            title="Carga de mañana",
            scheduled_date=date(2026, 10, 16),
            estimated_hours=Decimal("2.00"),
        )
        User.objects.filter(pk=self.user.pk).update(daily_hour_limit=Decimal("3.00"))

        updated = TaskService.postpone_task(task, self.user)

        self.assertEqual(updated.scheduled_date, date(2026, 10, 17))

    @patch("apps.tasks.services.timezone.localdate")
    def test_postpone_rejects_when_no_future_date_has_capacity(self, localdate):
        today = date(2026, 10, 15)
        localdate.return_value = today
        task = LogisticTask.objects.create(
            event=self.event,
            title="Tarea sin cupo",
            scheduled_date=today,
            estimated_hours=Decimal("2.00"),
        )
        for offset in range(1, 11):
            LogisticTask.objects.create(
                event=self.event,
                title=f"Bloqueo {offset}",
                scheduled_date=today + timedelta(days=offset),
                estimated_hours=Decimal("6.00"),
            )

        with self.assertRaises(DailyOverloadConflict):
            TaskService.postpone_task(task, self.user, "")

        task.refresh_from_db()
        self.assertEqual(task.scheduled_date, today)
        self.assertEqual(task.status, LogisticTask.Status.PENDING)
        self.assertEqual(task.notes, "")
        self.assertFalse(RescheduleHistory.objects.filter(task=task).exists())


class TaskRescheduleApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rescheduler",
            email="rescheduler@example.com",
            password="securepassword123",
        )
        self.event = Event.objects.create(
            user=self.user,
            title="Actividad de prueba",
            course="Proyecto Integrador",
            event_date=date.today() + timedelta(days=10),
        )
        self.task = LogisticTask.objects.create(
            event=self.event,
            title="Buscar proveedor",
            scheduled_date=date.today(),
            estimated_hours=Decimal("1.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_patch_scheduled_date_persists_the_reschedule(self):
        new_date = date.today() + timedelta(days=4)

        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}/",
            {"scheduled_date": new_date.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scheduled_date"], new_date.isoformat())
        self.task.refresh_from_db()
        self.assertEqual(self.task.scheduled_date, new_date)

    def test_patch_rejects_an_invalid_scheduled_date(self):
        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}/",
            {"scheduled_date": "not-a-date"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.task.refresh_from_db()
        self.assertEqual(self.task.scheduled_date, date.today())

    def test_task_list_includes_the_event_course_for_filters(self):
        response = self.client.get("/api/v1/tasks/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["event_title"], self.event.title)
        self.assertEqual(response.data["results"][0]["event_course"], self.event.course)

    def test_history_endpoint_returns_empty_list_without_history(self):
        response = self.client.get(f"/api/v1/tasks/{self.task.id}/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_history_endpoint_returns_serialized_history(self):
        new_date = date.today() + timedelta(days=2)
        TaskService.reschedule_task(
            task=self.task,
            user=self.user,
            new_date=new_date,
            new_hours=Decimal("2.00"),
            reason="Cambio de proveedor",
        )

        response = self.client.get(f"/api/v1/tasks/{self.task.id}/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["task"], self.task.id)
        self.assertEqual(response.data[0]["user"], self.user.id)
        self.assertEqual(response.data[0]["new_date"], new_date.isoformat())
        self.assertEqual(response.data[0]["new_hours"], "2.00")

    def test_history_endpoint_is_isolated_by_owner(self):
        other_user = User.objects.create_user(
            username="other-rescheduler",
            email="other@example.com",
            password="securepassword123",
        )
        client = APIClient()
        client.force_authenticate(other_user)

        response = client.get(f"/api/v1/tasks/{self.task.id}/history/")

        self.assertEqual(response.status_code, 404)

    def test_completion_note_is_trimmed_and_persisted(self):
        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}/",
            {"status": "completed", "completion_note": "  Todo listo  "},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.completion_note, "Todo listo")
        self.assertEqual(response.data["completion_note"], "Todo listo")
        event_response = self.client.get(f"/api/v1/events/{self.event.id}/")
        self.assertEqual(event_response.status_code, 200)
        self.assertEqual(event_response.data["tasks"][0]["completion_note"], "Todo listo")

    def test_completion_note_with_only_spaces_is_stored_as_null(self):
        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}/",
            {"status": "completed", "completion_note": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.completion_note)

    @patch("apps.tasks.services.timezone.localdate")
    def test_postpone_api_persists_date_status_and_note(self, localdate):
        today = date(2026, 10, 15)
        localdate.return_value = today
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/postpone/",
            {"note": "Cambio de proveedor"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.scheduled_date, today + timedelta(days=1))
        self.assertEqual(self.task.status, LogisticTask.Status.POSTPONED)
        self.assertEqual(self.task.notes, "Cambio de proveedor")

    @patch("apps.tasks.services.timezone.localdate")
    def test_postpone_api_accepts_empty_note(self, localdate):
        today = date(2026, 10, 15)
        localdate.return_value = today
        response = self.client.post(
            f"/api/v1/tasks/{self.task.id}/postpone/",
            {"note": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.notes, "")


class ConcurrentTaskPostponeTest(TransactionTestCase):
    reset_sequences = True

    @patch("apps.tasks.services.timezone.localdate", return_value=date(2026, 10, 15))
    def test_simultaneous_postpones_get_distinct_capacity_slots(self, _localdate):
        user = User.objects.create_user(
            username="parallel",
            email="parallel@example.com",
            password="securepassword123",
            daily_hour_limit=Decimal("2.00"),
        )
        event = Event.objects.create(
            user=user,
            title="Evento concurrente",
            event_date=date(2026, 10, 25),
        )
        tasks = [
            LogisticTask.objects.create(
                event=event,
                title=f"Subtarea {index}",
                scheduled_date=date(2026, 10, 15),
                estimated_hours=Decimal("2.00"),
            )
            for index in range(2)
        ]
        start = Barrier(2)

        def postpone(task_id):
            close_old_connections()
            try:
                start.wait(timeout=10)
                current_user = User.objects.get(pk=user.pk)
                current_task = LogisticTask.objects.get(pk=task_id)
                return TaskService.postpone_task(current_task, current_user).scheduled_date
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            dates = list(pool.map(postpone, [task.id for task in tasks]))

        self.assertEqual(len(set(dates)), 2)
