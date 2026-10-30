"""Root URL configuration."""
from django.urls import include, path


urlpatterns = [
    path("api/v1/", include(([], "api"), namespace="v1")),
]
