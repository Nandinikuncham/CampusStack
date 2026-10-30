from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    department = models.CharField(max_length=120)
    batch_start_year = models.PositiveSmallIntegerField()
    batch_end_year = models.PositiveSmallIntegerField()
    admission_date = models.DateField()
    expected_graduation_date = models.DateField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(batch_end_year__gte=F("batch_start_year")),
                name="profiles_student_batch_end_gte_start",
            ),
            models.CheckConstraint(
                condition=Q(expected_graduation_date__gte=F("admission_date")),
                name="profiles_student_graduation_after_admission",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.user_id and self.user.account_type != self.user.AccountType.STUDENT:
            errors["user"] = "Student profiles must belong to student accounts."
        if self.batch_end_year is not None and self.batch_start_year is not None:
            if self.batch_end_year < self.batch_start_year:
                errors["batch_end_year"] = "Batch end year cannot precede batch start year."
        if self.admission_date and self.expected_graduation_date:
            if self.expected_graduation_date < self.admission_date:
                errors["expected_graduation_date"] = (
                    "Expected graduation cannot precede admission."
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Student profile: {self.user.email}"


class FacultyProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="faculty_profile",
    )
    department = models.CharField(max_length=120)
    designation = models.CharField(max_length=120)
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="faculty_approvals",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        approval_status="APPROVED",
                        approved_by__isnull=False,
                        approved_at__isnull=False,
                    )
                    | (
                        ~Q(approval_status="APPROVED")
                        & Q(approved_by__isnull=True, approved_at__isnull=True)
                    )
                ),
                name="profiles_faculty_approval_fields_consistent",
            ),
        ]

    def clean(self):
        super().clean()
        if self.user_id and self.user.account_type != self.user.AccountType.FACULTY:
            raise ValidationError({"user": "Faculty profiles must belong to faculty accounts."})
        if self.approval_status == self.ApprovalStatus.APPROVED:
            if not self.approved_by or not self.approved_at:
                raise ValidationError(
                    "Approved faculty profiles require an approver and approval time."
                )
            if self.approved_by.account_type != self.approved_by.AccountType.ADMIN:
                raise ValidationError({"approved_by": "Approver must be an administrator."})
        elif self.approved_by_id or self.approved_at:
            raise ValidationError(
                "Only approved profiles may have an approver and approval time."
            )

    def __str__(self):
        return f"Faculty profile: {self.user.email} ({self.approval_status})"
