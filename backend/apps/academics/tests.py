from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.profiles.models import StudentProfile

from .models import AcademicCalendar
from .services import AcademicProgressionError, AcademicStatus, calculate_academic_status


class AcademicProgressionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user("student@example.com", "pw")
        self.profile = StudentProfile.objects.create(
            user=self.student,
            department="Computer Science",
            batch_start_year=2023,
            batch_end_year=2027,
            admission_date=date(2023, 8, 1),
            expected_graduation_date=date(2027, 6, 30),
        )
        for label, starts, ends, current in (
            ("2023-2024", date(2023, 8, 15), date(2024, 6, 30), False),
            ("2024-2025", date(2024, 8, 15), date(2025, 6, 30), False),
            ("2025-2026", date(2025, 8, 15), date(2026, 6, 30), True),
        ):
            AcademicCalendar.objects.create(
                academic_year=label,
                starts_on=starts,
                ends_on=ends,
                is_current=current,
            )

    def test_first_and_second_years_are_junior(self):
        self.assertEqual(
            calculate_academic_status(self.profile, as_of=date(2023, 9, 1)),
            AcademicStatus.JUNIOR,
        )
        self.assertEqual(
            calculate_academic_status(self.profile, as_of=date(2025, 1, 1)),
            AcademicStatus.JUNIOR,
        )

    def test_third_year_promotion_follows_calendar_start_not_january(self):
        self.assertEqual(
            calculate_academic_status(self.profile, as_of=date(2025, 1, 1)),
            AcademicStatus.JUNIOR,
        )
        self.assertEqual(
            calculate_academic_status(self.profile, as_of=date(2025, 8, 15)),
            AcademicStatus.SENIOR,
        )

    def test_alumni_status_starts_after_configured_graduation_date(self):
        self.assertEqual(
            calculate_academic_status(self.profile, as_of=date(2027, 6, 30)),
            AcademicStatus.SENIOR,
        )
        self.assertEqual(
            calculate_academic_status(self.profile, as_of=date(2027, 7, 1)),
            AcademicStatus.ALUMNI,
        )

    def test_missing_calendar_does_not_guess_a_promotion_date(self):
        AcademicCalendar.objects.all().delete()

        with self.assertRaises(AcademicProgressionError):
            calculate_academic_status(self.profile, as_of=date(2023, 1, 1))

    def test_invalid_calendar_dates_fail_validation(self):
        calendar = AcademicCalendar(
            academic_year="2030-2031",
            starts_on=date(2031, 1, 1),
            ends_on=date(2030, 12, 31),
        )

        with self.assertRaises(ValidationError):
            calendar.full_clean()
