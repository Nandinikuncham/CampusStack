"""Root URL configuration."""
from django.urls import include, path


urlpatterns = [
    path("api/v1/", include(("apps.accounts.api_urls", "api"), namespace="v1")),
]
