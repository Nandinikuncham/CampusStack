from rest_framework.permissions import BasePermission

from .models import User


class IsCampusAdministrator(BasePermission):
    """Allow access only to active, authenticated CampusStack administrators."""

    message = "Administrator privileges are required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.account_type == User.AccountType.ADMIN
        )
