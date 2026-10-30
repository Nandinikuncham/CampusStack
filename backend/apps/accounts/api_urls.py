from django.urls import include, path

from apps.profiles.views import CurrentProfileView, PublicProfileView

from .views import (
    CSRFTokenView,
    CurrentUserView,
    FacultyRegistrationView,
    LoginView,
    LogoutView,
    StudentRegistrationView,
)


app_name = "auth"

urlpatterns = [
    path("auth/csrf/", CSRFTokenView.as_view(), name="csrf"),
    path("auth/register/student/", StudentRegistrationView.as_view(), name="register-student"),
    path("auth/register/faculty/", FacultyRegistrationView.as_view(), name="register-faculty"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", CurrentUserView.as_view(), name="me"),
    path("users/<int:user_id>/profile/", PublicProfileView.as_view(), name="public-profile"),
    path("profiles/me/", CurrentProfileView.as_view(), name="current-profile"),
    path("", include("apps.social.urls")),
    path("", include("apps.questions.api_urls")),
]
