from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User

from .models import FacultyProfile, StudentProfile
from .services import approve_faculty_profile


class ProfileModelTests(TestCase):
    def test_student_and_faculty_profiles_are_one_to_one(self):
        student = User.objects.create_user("student@example.com", "pw")
        faculty = User.objects.create_user(
            "faculty@example.com", "pw", account_type=User.AccountType.FACULTY
        )
        student_profile = StudentProfile.objects.create(
            user=student,
            department="Computer Science",
            batch_start_year=2023,
            batch_end_year=2027,
            admission_date=date(2023, 8, 1),
            expected_graduation_date=date(2027, 6, 30),
        )
        faculty_profile = FacultyProfile.objects.create(
            user=faculty,
            department="Computer Science",
            designation="Lecturer",
        )

        self.assertEqual(student.student_profile, student_profile)
        self.assertEqual(faculty.faculty_profile, faculty_profile)
        self.assertEqual(faculty_profile.approval_status, FacultyProfile.ApprovalStatus.PENDING)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentProfile.objects.create(
                    user=student,
                    department="Mathematics",
                    batch_start_year=2023,
                    batch_end_year=2027,
                    admission_date=date(2023, 8, 1),
                    expected_graduation_date=date(2027, 6, 30),
                )

    def test_invalid_batch_dates_fail_validation(self):
        student = User.objects.create_user("student@example.com", "pw")
        profile = StudentProfile(
            user=student,
            department="Computer Science",
            batch_start_year=2024,
            batch_end_year=2023,
            admission_date=date(2024, 8, 1),
            expected_graduation_date=date(2024, 7, 1),
        )

        with self.assertRaises(ValidationError) as context:
            profile.full_clean()

        self.assertIn("batch_end_year", context.exception.message_dict)
        self.assertIn("expected_graduation_date", context.exception.message_dict)


class FacultyApprovalTests(TestCase):
    def setUp(self):
        self.faculty = User.objects.create_user(
            "faculty@example.com", "pw", account_type=User.AccountType.FACULTY
        )
        self.profile = FacultyProfile.objects.create(
            user=self.faculty,
            department="Physics",
            designation="Assistant Professor",
        )
        self.student = User.objects.create_user("student@example.com", "pw")
        self.administrator = User.objects.create_superuser(
            "admin@example.com", "pw"
        )

    def test_only_administrator_can_approve_and_approval_is_audited(self):
        with self.assertRaises(PermissionDenied):
            approve_faculty_profile(
                faculty_profile=self.profile,
                administrator=self.student,
            )

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, FacultyProfile.ApprovalStatus.PENDING)

        approved = approve_faculty_profile(
            faculty_profile=self.profile,
            administrator=self.administrator,
        )
        self.assertEqual(approved.approval_status, FacultyProfile.ApprovalStatus.APPROVED)
        self.assertEqual(approved.approved_by, self.administrator)
        self.assertIsNotNone(approved.approved_at)

        from apps.audit.models import AuditEvent

        event = AuditEvent.objects.get(action="faculty.approved")
        self.assertEqual(event.actor, self.administrator)
        self.assertEqual(event.target_user, self.faculty)
        self.assertEqual(event.metadata, {"faculty_profile_id": self.profile.pk})
