from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.models import User


class IsAuthorOrCampusAdministrator(BasePermission):
    """Allow content writes only to its author or a CampusStack administrator."""

    message = "Only the content author or an administrator may modify this content."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user.is_authenticated
            and (
                obj.author_id == request.user.pk
                or request.user.account_type == User.AccountType.ADMIN
            )
        )
