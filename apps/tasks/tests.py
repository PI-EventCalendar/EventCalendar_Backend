from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

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
        self.assertEqual(updated_task.status, LogisticTask.Status.POSTPONED)

        history = RescheduleHistory.objects.filter(task=task).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.previous_date, original_date)
        self.assertEqual(history.new_date, new_date)
        self.assertEqual(history.previous_hours, Decimal("3.00"))
        self.assertEqual(history.new_hours, Decimal("2.50"))
        self.assertEqual(history.reason, "Retraso en el envío de equipos")
