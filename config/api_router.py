from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.events.views import EventViewSet
from apps.tasks.dashboard_views import DailyLoadView, TodayTasksView
from apps.tasks.views import LogisticTaskViewSet, TaskCategoryViewSet

# Router principal DRF
router = DefaultRouter()
router.register(r"events", EventViewSet, basename="event")
router.register(r"categories", TaskCategoryViewSet, basename="category")
router.register(r"tasks", LogisticTaskViewSet, basename="task")

# Ensamblado de endpoints bajo /api/v1/
urlpatterns = [
    path("auth/", include("apps.users.urls")),
    path("dashboard/today/", TodayTasksView.as_view(), name="dashboard-today"),
    path("dashboard/load/", DailyLoadView.as_view(), name="dashboard-load"),
    path("", include(router.urls)),
]
