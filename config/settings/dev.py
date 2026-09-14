"""Development settings for EventCalendar."""

from .base import *  # noqa: F403
import os

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Useful dev settings
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
