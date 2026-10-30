from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class UserFollow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_edges",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follower_edges",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("follower", "following"),
                name="social_unique_user_follow",
            ),
            models.CheckConstraint(
                condition=~Q(follower=F("following")),
                name="social_no_self_follow",
            ),
        ]
        indexes = [
            models.Index(fields=("following", "-created_at"), name="social_followers_date_idx"),
            models.Index(fields=("follower", "-created_at"), name="social_following_date_idx"),
        ]

    def clean(self):
        super().clean()
        if self.follower_id and self.follower_id == self.following_id:
            raise ValidationError("Users cannot follow themselves.")


class TagFollow(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tag_follow_edges",
    )
    tag = models.ForeignKey(
        "questions.Tag",
        on_delete=models.CASCADE,
        related_name="social_followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "tag"),
                name="social_unique_tag_follow",
            ),
        ]


class MentorshipRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentorship_requests_sent",
    )
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentorship_requests_received",
    )
    message = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(student=F("mentor")),
                name="social_no_self_request",
            ),
            models.CheckConstraint(
                condition=Q(status__in=("PENDING", "APPROVED", "REJECTED", "CANCELLED", "COMPLETED")),
                name="social_request_status_valid",
            ),
            models.CheckConstraint(
                condition=~Q(message=""),
                name="social_request_message_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="PENDING", resolved_at__isnull=True)
                    | (~Q(status="PENDING") & Q(resolved_at__isnull=False))
                ),
                name="social_request_resolution_valid",
            ),
            models.UniqueConstraint(
                fields=("student", "mentor"),
                condition=Q(status="PENDING"),
                name="social_one_pending_request",
            ),
        ]
        indexes = [
            models.Index(fields=("student", "status", "created_at"), name="social_request_sent_idx"),
            models.Index(fields=("mentor", "status", "created_at"), name="social_request_received_idx"),
        ]

    def clean(self):
        super().clean()
        if self.student_id and self.student_id == self.mentor_id:
            raise ValidationError("Users cannot request mentorship from themselves.")
        if self.message and not self.message.strip():
            raise ValidationError({"message": "A mentorship request message is required."})


class Mentorship(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"

    request = models.OneToOneField(
        MentorshipRequest,
        on_delete=models.PROTECT,
        related_name="relationship",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentorships_as_student",
    )
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentorships_as_mentor",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(student=F("mentor")),
                name="social_no_self_mentorship",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="ACTIVE", completed_at__isnull=True)
                    | Q(status="COMPLETED", completed_at__isnull=False)
                ),
                name="social_mentorship_time_valid",
            ),
            models.UniqueConstraint(
                fields=("student", "mentor"),
                condition=Q(status="ACTIVE"),
                name="social_one_active_mentor_pair",
            ),
        ]
        indexes = [
            models.Index(fields=("student", "status", "started_at"), name="social_mentee_rel_idx"),
            models.Index(fields=("mentor", "status", "started_at"), name="social_mentor_rel_idx"),
        ]

    def clean(self):
        super().clean()
        if self.request_id and (self.student_id != self.request.student_id or self.mentor_id != self.request.mentor_id):
            raise ValidationError("Mentorship participants must match the approved request.")
        if self.request_id and self.request.status not in {
            MentorshipRequest.Status.APPROVED,
            MentorshipRequest.Status.COMPLETED,
        }:
            raise ValidationError("A mentorship requires an approved request.")
