from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CustomTokenObtainPairView, ProfileView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="user-register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # Consultar y actualizar el perfil del usuario autenticado.
    # Incluye el campo daily_hour_limit.
    path("profile/", ProfileView.as_view(), name="user-profile"),
]
