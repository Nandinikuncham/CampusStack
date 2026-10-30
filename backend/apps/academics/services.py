from datetime import date

from django.utils import timezone

from .models import AcademicCalendar


class AcademicProgressionError(ValueError):
    """Raised when the configured calendar cannot determine progression."""


class AcademicStatus:
    JUNIOR = "JUNIOR"
    SENIOR = "SENIOR"
    ALUMNI = "ALUMNI"


def calculate_academic_status(student_profile, *, as_of: date | None = None) -> str:
    """Calculate, but never persist, a student's status from calendar boundaries."""
    reference_date = as_of or timezone.localdate()

    if reference_date > student_profile.expected_graduation_date:
        return AcademicStatus.ALUMNI

    calendar = (
        AcademicCalendar.objects.filter(starts_on__lte=reference_date)
        .order_by("-starts_on")
        .first()
    )
    if calendar is None:
        raise AcademicProgressionError(
            f"No academic calendar is configured on or before {reference_date}."
        )

    academic_year_number = calendar.starts_on.year - student_profile.batch_start_year + 1
    if academic_year_number < 1:
        raise AcademicProgressionError(
            "The configured academic calendar predates this student's batch."
        )
    if academic_year_number <= 2:
        return AcademicStatus.JUNIOR
    return AcademicStatus.SENIOR
