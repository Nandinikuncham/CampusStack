from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent

from .models import FacultyProfile


@transaction.atomic
def approve_faculty_profile(*, faculty_profile, administrator):
    """Approve a pending faculty profile and record the sensitive action."""
    if not (
        administrator
        and administrator.is_authenticated
        and administrator.is_active
        and administrator.account_type == User.AccountType.ADMIN
    ):
        raise PermissionDenied("Only an active CampusStack administrator may approve faculty.")

    if faculty_profile.approval_status != FacultyProfile.ApprovalStatus.PENDING:
        raise ValidationError("Only pending faculty profiles can be approved.")

    faculty_profile.approval_status = FacultyProfile.ApprovalStatus.APPROVED
    faculty_profile.approved_by = administrator
    faculty_profile.approved_at = timezone.now()
    faculty_profile.full_clean()
    faculty_profile.save(update_fields=("approval_status", "approved_by", "approved_at"))

    AuditEvent.objects.create(
        actor=administrator,
        action="faculty.approved",
        target_user=faculty_profile.user,
        metadata={"faculty_profile_id": faculty_profile.pk},
    )
    return faculty_profile
