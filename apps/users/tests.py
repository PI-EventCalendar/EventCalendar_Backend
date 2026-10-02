from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


User = get_user_model()


class CapacityApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="capacity-user", email="capacity@example.com", password="securepassword123"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_default_capacity_is_six_hours(self):
        response = self.client.get("/api/v1/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["daily_hour_limit"]), Decimal("6.00"))

    def test_capacity_accepts_one_to_sixteen_and_persists(self):
        response = self.client.patch("/api/v1/auth/profile/", {"daily_hour_limit": "4.00"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_hour_limit, Decimal("4.00"))

    def test_capacity_rejects_values_outside_range(self):
        for value in (0, -1, 17, 20):
            response = self.client.patch("/api/v1/auth/profile/", {"daily_hour_limit": value}, format="json")
            self.assertEqual(response.status_code, 400)


class RegistrationApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "username": "juan123", "email": "juan@example.com",
            "password": "securepassword123", "password_confirm": "securepassword123",
            "first_name": "Juan", "last_name": "Rojas",
        }

    def test_registration_creates_profile_and_tokens(self):
        response = self.client.post("/api/v1/auth/register/", self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data["tokens"])
        self.assertTrue(User.objects.filter(username="juan123").exists())

    def test_duplicate_username_and_email_are_rejected(self):
        User.objects.create_user(username="juan123", email="juan@example.com", password="securepassword123")
        response = self.client.post("/api/v1/auth/register/", self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)

    def test_same_names_are_allowed_with_new_identity(self):
        User.objects.create_user(username="juan123", email="juan@example.com", password="securepassword123", first_name="Juan", last_name="Rojas")
        payload = {**self.payload, "username": "juan456", "email": "otro@example.com"}
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, 201)
