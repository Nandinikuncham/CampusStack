from django.urls import path

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
]
