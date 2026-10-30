from rest_framework.permissions import BasePermission

from apps.profiles.models import FacultyProfile

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


class IsApprovedFaculty(BasePermission):
    """Allow only active faculty with an approved profile."""

    message = "An approved faculty account is required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (
            user
            and user.is_authenticated
            and user.is_active
            and user.account_type == User.AccountType.FACULTY
        ):
            return False
        try:
            return user.faculty_profile.approval_status == FacultyProfile.ApprovalStatus.APPROVED
        except FacultyProfile.DoesNotExist:
            return False
