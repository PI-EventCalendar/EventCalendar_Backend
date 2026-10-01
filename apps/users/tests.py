from django.test import TestCase
from rest_framework.test import APIClient

from .models import User


class RegistrationApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "username": "juan123",
            "email": "juan@example.com",
            "password": "securepassword123",
            "password_confirm": "securepassword123",
            "first_name": "Juan",
            "last_name": "Rojas",
        }

    def test_registration_returns_tokens_and_creates_profile(self):
        response = self.client.post("/api/v1/auth/register/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertTrue(User.objects.filter(username="juan123", email="juan@example.com").exists())

    def test_duplicate_username_and_email_are_rejected(self):
        User.objects.create_user(
            username="juan123",
            email="juan@example.com",
            password="securepassword123",
        )

        response = self.client.post("/api/v1/auth/register/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)

    def test_same_name_and_last_name_are_allowed_with_new_identity(self):
        User.objects.create_user(
            username="juan123",
            email="juan@example.com",
            password="securepassword123",
            first_name="Juan",
            last_name="Rojas",
        )
        payload = {**self.payload, "username": "juan456", "email": "otro@example.com"}

        response = self.client.post("/api/v1/auth/register/", payload, format="json")

        self.assertEqual(response.status_code, 201)
