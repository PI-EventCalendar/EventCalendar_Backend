from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

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
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

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

    def test_update_event_accepts_new_nested_task_without_fake_id(self):
        response = self.client.patch(
            f"/api/v1/events/{self.event.id}/",
            {
                "title": self.event.title,
                "event_date": str(self.event.event_date),
                "tasks": [
                    {
                        "title": "Nueva subtarea",
                        "scheduled_date": str(date.today()),
                        "estimated_hours": "2.00",
                        "status": "pending",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.event.tasks.count(), 1)
        self.assertEqual(self.event.tasks.first().title, "Nueva subtarea")

    def test_update_event_uses_global_capacity_from_other_events(self):
        other = Event.objects.create(
            user=self.user, title="Otro", event_date=date.today()
        )
        LogisticTask.objects.create(
            event=other,
            title="Existente",
            scheduled_date=date.today(),
            estimated_hours=Decimal("5.00"),
        )
        response = self.client.patch(
            f"/api/v1/events/{self.event.id}/",
            {
                "tasks": [
                    {
                        "title": "Nueva",
                        "scheduled_date": str(date.today()),
                        "estimated_hours": "1.01",
                        "status": "pending",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409, response.data)

    def test_update_event_allows_global_capacity_exact_limit(self):
        other = Event.objects.create(
            user=self.user, title="Otro", event_date=date.today()
        )
        LogisticTask.objects.create(
            event=other,
            title="Existente",
            scheduled_date=date.today(),
            estimated_hours=Decimal("5.00"),
        )
        response = self.client.patch(
            f"/api/v1/events/{self.event.id}/",
            {
                "tasks": [
                    {
                        "title": "Nueva",
                        "scheduled_date": str(date.today()),
                        "estimated_hours": "1.00",
                        "status": "pending",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_create_event_uses_global_capacity(self):
        other = Event.objects.create(
            user=self.user, title="Otro", event_date=date.today()
        )
        LogisticTask.objects.create(
            event=other,
            title="Existente",
            scheduled_date=date.today(),
            estimated_hours=Decimal("5.00"),
        )
        response = self.client.post(
            "/api/v1/events/",
            {
                "title": "Nuevo",
                "activity_type": "Conferencia",
                "event_date": str(date.today()),
                "tasks": [
                    {
                        "title": "Nueva",
                        "scheduled_date": str(date.today()),
                        "estimated_hours": "1.01",
                        "status": "pending",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409, response.data)

    def test_event_location_persists_and_is_returned(self):
        response = self.client.post(
            "/api/v1/events/",
            {
                "title": "Con lugar",
                "activity_type": "Conferencia",
                "event_date": str(date.today()),
                "location": "Finca El Encinar",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["location"], "Finca El Encinar")
        self.assertEqual(
            self.client.get(f"/api/v1/events/{response.data['id']}/").data["location"],
            "Finca El Encinar",
        )


class EventNestedTasksValidationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="eventorganizer",
            email="organizer@example.com",
            password="testpassword123",
            daily_hour_limit=Decimal("6.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_event_with_nested_task_past_event_date_fails(self):
        event_date = date.today() + timedelta(days=5)
        invalid_task_date = event_date + timedelta(days=1)
        response = self.client.post(
            "/api/v1/events/",
            {
                "title": "Conferencia de Negocios",
                "event_date": event_date.isoformat(),
                "activity_type": "Conferencia",
                "tasks": [
                    {
                        "title": "Tarea Tardía",
                        "scheduled_date": invalid_task_date.isoformat(),
                        "estimated_hours": "2.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("tasks", response.data)

    def test_create_event_with_nested_task_on_or_before_event_date_succeeds(self):
        event_date = date.today() + timedelta(days=5)
        valid_task_date = event_date
        response = self.client.post(
            "/api/v1/events/",
            {
                "title": "Conferencia Exitosa",
                "event_date": event_date.isoformat(),
                "activity_type": "Conferencia",
                "tasks": [
                    {
                        "title": "Tarea a Tiempo",
                        "scheduled_date": valid_task_date.isoformat(),
                        "estimated_hours": "2.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
