"""Main URL Configuration for EventCalendar."""

from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
# Vista simple para responder en la raíz "/"
@api_view(['GET'])
@permission_classes([AllowAny])
def root_view(request):
    return Response({
        "status": "online",
        "message": "Bienvenido a la API de EventCalendar",
        "version": "v1",
        "endpoints": "/api/v1/"
    })

urlpatterns = [
    path('', root_view, name='api-root-index'),

    path('admin/', admin.site.urls),

    path('api/v1/', include('config.api_router')),
    path('api/v1/auth/', include('apps.users.urls')),

    path(
        'api/schema/',
        SpectacularAPIView.as_view(),
        name='schema'
    ),

    path(
        'api/schema/swagger-ui/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui'
    ),

    path(
        'api/schema/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc'
    ),
]
