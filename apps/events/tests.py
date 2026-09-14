from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.events.models import Event
from apps.events.services import EventService
from apps.tasks.models import LogisticTask

User = get_user_model()


class EventProgressServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
            daily_hour_limit=Decimal("6.00"),
        )
        self.event = Event.objects.create(
            user=self.user,
            title="Evento de Prueba",
            event_date=date.today(),
        )

    def test_progress_with_no_tasks(self):
        events = EventService.get_events_for_user(self.user)
        metrics = EventService.calculate_progress(events.first())
        self.assertEqual(metrics["total_tasks"], 0)
        self.assertEqual(metrics["completed_tasks"], 0)
        self.assertEqual(metrics["progress_percentage"], 0.0)

    def test_progress_with_mixed_tasks(self):
        LogisticTask.objects.create(
            event=self.event,
            title="Tarea 1",
            scheduled_date=date.today(),
            estimated_hours=Decimal("2.00"),
            status=LogisticTask.Status.COMPLETED,
        )
        LogisticTask.objects.create(
            event=self.event,
            title="Tarea 2",
            scheduled_date=date.today(),
            estimated_hours=Decimal("3.00"),
            status=LogisticTask.Status.PENDING,
        )
        events = EventService.get_events_for_user(self.user)
        metrics = EventService.calculate_progress(events.first())
        self.assertEqual(metrics["total_tasks"], 2)
        self.assertEqual(metrics["completed_tasks"], 1)
        self.assertEqual(metrics["progress_percentage"], 50.0)
