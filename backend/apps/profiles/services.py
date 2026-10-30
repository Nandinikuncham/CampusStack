from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.questions.models import Answer, Comment, Question

from .models import FacultyProfile


def with_contribution_statistics(queryset=None):
    """Annotate users with contribution counts using one correlated subquery per metric."""
    queryset = queryset if queryset is not None else User.objects.all()

    def count_for(model, relationship, *, accepted_only=False):
        items = model.objects.filter(**{relationship: OuterRef("pk")})
        if accepted_only:
            items = items.filter(is_accepted=True)
        return Coalesce(
            Subquery(
                items.order_by()
                .values(relationship)
                .annotate(total=Count("pk"))
                .values("total")[:1],
                output_field=IntegerField(),
            ),
            Value(0),
            output_field=IntegerField(),
        )

    return queryset.select_related("student_profile", "faculty_profile").annotate(
        questions_asked=count_for(Question, "author_id"),
        answers_posted=count_for(Answer, "author_id"),
        accepted_answers=count_for(Answer, "author_id", accepted_only=True),
        comments_posted=count_for(Comment, "author_id"),
        follower_count=Count("follower_edges", distinct=True),
        following_count=Count("following_edges", distinct=True),
    )


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
