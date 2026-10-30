from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.academics.services import (
    AcademicProgressionError,
    AcademicStatus,
    calculate_academic_status,
)
from apps.audit.models import AuditEvent
from apps.profiles.models import FacultyProfile, StudentProfile

from .models import Mentorship, MentorshipRequest, TagFollow, UserFollow


@transaction.atomic
def follow_user(*, follower, target):
    if follower.pk == target.pk:
        raise ValidationError("Users cannot follow themselves.")
    relation, _ = UserFollow.objects.get_or_create(follower=follower, following=target)
    return relation


@transaction.atomic
def unfollow_user(*, follower, target):
    UserFollow.objects.filter(follower=follower, following=target).delete()


@transaction.atomic
def follow_tag(*, user, tag):
    relation, _ = TagFollow.objects.get_or_create(user=user, tag=tag)
    return relation


@transaction.atomic
def unfollow_tag(*, user, tag):
    TagFollow.objects.filter(user=user, tag=tag).delete()


def _student_academic_status(user):
    try:
        profile = StudentProfile.objects.get(user=user)
    except StudentProfile.DoesNotExist as exc:
        raise ValidationError("A student profile is required for mentorship.") from exc
    try:
        return calculate_academic_status(profile)
    except AcademicProgressionError as exc:
        raise ValidationError(
            "Academic status cannot be determined from the current calendar."
        ) from exc


def _validate_mentee(student):
    if not student.is_active or student.account_type != User.AccountType.STUDENT:
        raise ValidationError("Only active student accounts may request mentorship.")
    if _student_academic_status(student) not in {
        AcademicStatus.JUNIOR,
        AcademicStatus.SENIOR,
    }:
        raise ValidationError("Only junior or senior students may request mentorship.")


def _validate_mentor(mentor):
    if not mentor.is_active:
        raise ValidationError("Inactive accounts cannot act as mentors.")
    if mentor.account_type == User.AccountType.FACULTY:
        try:
            approved = (
                FacultyProfile.objects.filter(user=mentor)
                .values_list("approval_status", flat=True)
                .get()
                == FacultyProfile.ApprovalStatus.APPROVED
            )
        except FacultyProfile.DoesNotExist:
            approved = False
        if not approved:
            raise ValidationError("Only approved faculty may act as mentors.")
        return
    if mentor.account_type == User.AccountType.STUDENT:
        if _student_academic_status(mentor) not in {
            AcademicStatus.SENIOR,
            AcademicStatus.ALUMNI,
        }:
            raise ValidationError("Only senior or alumni students may act as mentors.")
        return
    raise ValidationError("This account type is not eligible to act as a mentor.")


@transaction.atomic
def create_mentorship_request(*, student, mentor, message):
    if student.pk == mentor.pk:
        raise ValidationError("Students cannot request mentorship from themselves.")
    message = (message or "").strip()
    if not message:
        raise ValidationError({"message": "Explain the purpose of the mentorship request."})
    locked_users = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in=(student.pk, mentor.pk))
        .order_by("pk")
    }
    student = locked_users.get(student.pk)
    mentor = locked_users.get(mentor.pk)
    if student is None or mentor is None:
        raise ValidationError("Student or mentor account no longer exists.")
    _validate_mentee(student)
    _validate_mentor(mentor)

    try:
        with transaction.atomic():
            request = MentorshipRequest(
                student=student,
                mentor=mentor,
                message=message,
            )
            request.full_clean()
            request.save(force_insert=True)
    except IntegrityError as exc:
        raise ValidationError(
            "A pending request already exists for this student and mentor."
        ) from exc

    AuditEvent.objects.create(
        actor=student,
        action="mentorship.requested",
        target_user=mentor,
        metadata={"mentorship_request_id": request.pk},
    )
    return request


@transaction.atomic
def transition_mentorship_request(*, request_id, actor, action):
    mentorship_request = (
        MentorshipRequest.objects.select_for_update()
        .select_related("student", "mentor")
        .get(pk=request_id)
    )
    if actor.pk not in {mentorship_request.student_id, mentorship_request.mentor_id}:
        raise PermissionDenied("This mentorship request is private.")
    if mentorship_request.status != MentorshipRequest.Status.PENDING:
        raise ValidationError("Only pending requests can be changed.")

    now = timezone.now()
    if action in {"approve", "reject"}:
        if actor.pk != mentorship_request.mentor_id:
            raise PermissionDenied("Only the intended mentor can approve or reject this request.")
        if action == "approve":
            _validate_mentee(mentorship_request.student)
            _validate_mentor(mentorship_request.mentor)
            if Mentorship.objects.filter(
                student=mentorship_request.student,
                mentor=mentorship_request.mentor,
                status=Mentorship.Status.ACTIVE,
            ).exists():
                raise ValidationError("An active mentorship already exists for this pair.")
            mentorship_request.status = MentorshipRequest.Status.APPROVED
            mentorship_request.resolved_at = now
            try:
                with transaction.atomic():
                    mentorship = Mentorship(
                        request=mentorship_request,
                        student=mentorship_request.student,
                        mentor=mentorship_request.mentor,
                    )
                    mentorship.full_clean()
                    mentorship.save(force_insert=True)
            except IntegrityError as exc:
                raise ValidationError("An active mentorship already exists for this pair.") from exc
            audit_action = "mentorship.approved"
        else:
            mentorship_request.status = MentorshipRequest.Status.REJECTED
            audit_action = "mentorship.rejected"
    elif action == "cancel":
        if actor.pk != mentorship_request.student_id:
            raise PermissionDenied("Only the requesting student can cancel this request.")
        mentorship_request.status = MentorshipRequest.Status.CANCELLED
        audit_action = "mentorship.cancelled"
    else:
        raise ValidationError("Unsupported mentorship request transition.")

    mentorship_request.resolved_at = now
    mentorship_request.save(update_fields=("status", "resolved_at", "updated_at"))
    AuditEvent.objects.create(
        actor=actor,
        action=audit_action,
        target_user=mentorship_request.student,
        metadata={
            "mentorship_request_id": mentorship_request.pk,
            "status": mentorship_request.status,
        },
    )
    return mentorship_request


@transaction.atomic
def complete_mentorship(*, mentorship_id, actor):
    mentorship = (
        Mentorship.objects.select_for_update()
        .select_related("student", "mentor", "request")
        .get(pk=mentorship_id)
    )
    if actor.pk not in {mentorship.student_id, mentorship.mentor_id}:
        raise PermissionDenied("This mentorship is private.")
    if mentorship.status != Mentorship.Status.ACTIVE:
        raise ValidationError("Only active mentorships can be completed.")

    now = timezone.now()
    mentorship.status = Mentorship.Status.COMPLETED
    mentorship.completed_at = now
    mentorship.save(update_fields=("status", "completed_at"))
    mentorship.request.status = MentorshipRequest.Status.COMPLETED
    mentorship.request.resolved_at = now
    mentorship.request.save(update_fields=("status", "resolved_at", "updated_at"))
    AuditEvent.objects.create(
        actor=actor,
        action="mentorship.completed",
        target_user=mentorship.student if actor.pk == mentorship.mentor_id else mentorship.mentor,
        metadata={"mentorship_id": mentorship.pk},
    )
    return mentorship
