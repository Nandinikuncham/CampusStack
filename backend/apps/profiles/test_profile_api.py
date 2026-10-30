from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.academics.models import AcademicCalendar
from apps.questions.models import Answer, Comment, Question
from apps.questions.services import cast_vote

from .models import FacultyProfile, StudentProfile


class ProfileAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Strong-Profile-Test-Passphrase-72!"
        cls.student = User.objects.create_user(
            "profile-student@gvpcew.ac.in",
            cls.password,
            first_name="Mira",
            last_name="Student",
        )
        cls.student_profile = StudentProfile.objects.create(
            user=cls.student,
            department="Computer Science",
            batch_start_year=2024,
            batch_end_year=2028,
            admission_date=date(2024, 8, 1),
            expected_graduation_date=date(2028, 6, 30),
            biography="Learning backend development.",
            profile_image_url="https://example.com/mira.png",
        )
        cls.faculty = User.objects.create_user(
            "profile-faculty@gvpcew.ac.in",
            cls.password,
            account_type=User.AccountType.FACULTY,
            first_name="Asha",
            last_name="Faculty",
        )
        cls.faculty_profile = FacultyProfile.objects.create(
            user=cls.faculty,
            department="Physics",
            designation="Lecturer",
        )
        cls.other_user = User.objects.create_user("profile-other@gvpcew.ac.in", cls.password)
        AcademicCalendar.objects.create(
            academic_year="2026-2027",
            starts_on=date(2026, 8, 1),
            ends_on=date(2027, 6, 30),
            is_current=True,
        )

    def client_for(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        csrf = client.get("/api/v1/auth/csrf/")
        self.assertEqual(csrf.status_code, 200)
        client.csrf_token = csrf.json()["csrf_token"]
        return client

    def patch(self, client, payload):
        return client.patch(
            "/api/v1/profiles/me/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=client.csrf_token,
        )

    def test_public_student_profile_hides_private_fields_and_calculates_status(self):
        response = APIClient().get(f"/api/v1/users/{self.student.pk}/profile/")

        self.assertEqual(response.status_code, 200)
        profile = response.json()
        self.assertEqual(profile["display_name"], "Mira Student")
        self.assertEqual(profile["account_type"], "STUDENT")
        self.assertEqual(profile["department"], "Computer Science")
        self.assertEqual(profile["academic_status"], "SENIOR")
        self.assertEqual(profile["batch_start_year"], 2024)
        self.assertEqual(profile["batch_end_year"], 2028)
        self.assertEqual(profile["biography"], "Learning backend development.")
        self.assertEqual(profile["profile_image_url"], "https://example.com/mira.png")
        self.assertNotIn("email", profile)
        self.assertNotIn("password", profile)
        self.assertNotIn("approval_status", profile)

    def test_public_faculty_profile_serializes_professional_fields_only(self):
        response = APIClient().get(f"/api/v1/users/{self.faculty.pk}/profile/")

        self.assertEqual(response.status_code, 200)
        profile = response.json()
        self.assertEqual(profile["designation"], "Lecturer")
        self.assertEqual(profile["department"], "Physics")
        self.assertIsNone(profile["academic_status"])
        self.assertNotIn("approval_status", profile)
        self.assertNotIn("email", profile)

    def test_profile_endpoints_allow_public_read_and_require_auth_for_self(self):
        anonymous = APIClient(enforce_csrf_checks=True)
        self.assertEqual(
            anonymous.get(f"/api/v1/users/{self.student.pk}/profile/").status_code,
            200,
        )
        self.assertEqual(anonymous.get("/api/v1/profiles/me/").status_code, 403)
        self.assertEqual(anonymous.patch("/api/v1/profiles/me/", {}, format="json").status_code, 403)

        response = self.client_for(self.student).get("/api/v1/profiles/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], self.student.email)
        self.assertNotIn("password", response.json())

    def test_profile_updates_keep_session_csrf_protection(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.student)

        response = client.patch(
            "/api/v1/profiles/me/",
            {"biography": "Must include CSRF token."},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.biography, "Learning backend development.")

    def test_owner_can_update_personal_fields_and_faculty_designation(self):
        student_response = self.patch(
            self.client_for(self.student),
            {
                "first_name": "Mira Updated",
                "biography": "Interested in databases.",
                "profile_image_url": "https://example.com/new.png",
            },
        )
        self.assertEqual(student_response.status_code, 200, student_response.content)
        self.student.refresh_from_db()
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student.first_name, "Mira Updated")
        self.assertEqual(self.student_profile.biography, "Interested in databases.")

        faculty_response = self.patch(
            self.client_for(self.faculty),
            {"designation": "Associate Professor", "biography": "Researcher."},
        )
        self.assertEqual(faculty_response.status_code, 200, faculty_response.content)
        self.faculty_profile.refresh_from_db()
        self.assertEqual(self.faculty_profile.designation, "Associate Professor")
        self.assertEqual(self.faculty_profile.biography, "Researcher.")

    def test_protected_fields_and_cross_user_update_attempts_are_rejected(self):
        response = self.patch(
            self.client_for(self.student),
            {
                "account_type": "ADMIN",
                "department": "Changed",
                "academic_status": "ALUMNI",
                "batch_start_year": 1900,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.student.refresh_from_db()
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student.account_type, User.AccountType.STUDENT)
        self.assertEqual(self.student_profile.department, "Computer Science")
        self.assertEqual(self.student_profile.batch_start_year, 2024)

        other_client = self.client_for(self.other_user)
        cross_user_response = other_client.patch(
            f"/api/v1/users/{self.student.pk}/profile/",
            {"biography": "Cannot target another user."},
            format="json",
            HTTP_X_CSRFTOKEN=other_client.csrf_token,
        )
        self.assertEqual(cross_user_response.status_code, 405)
        self.assertEqual(self.student_profile.biography, "Learning backend development.")

    def test_missing_role_profile_returns_validation_error_for_profile_edits(self):
        response = self.patch(self.client_for(self.other_user), {"biography": "No profile row."})
        self.assertEqual(response.status_code, 400)
        self.assertIn("biography", response.json())

    def test_students_cannot_edit_faculty_only_fields_or_admin_fields(self):
        student_response = self.patch(self.client_for(self.student), {"designation": "Dean"})
        self.assertEqual(student_response.status_code, 400)

        admin = User.objects.create_superuser("profile-admin@gvpcew.ac.in", self.password)
        admin_response = self.patch(self.client_for(admin), {"biography": "Admin bio"})
        self.assertEqual(admin_response.status_code, 400)

    def test_contributions_and_existing_reputation_summary_are_integrated(self):
        question = Question.objects.create(
            author=self.student,
            title="Contribution question",
            description="A useful profile statistics question.",
        )
        Answer.objects.create(
            question=question,
            author=self.student,
            body="An accepted contribution.",
            is_accepted=True,
        )
        Comment.objects.create(
            author=self.student,
            question=question,
            content="A helpful comment.",
        )
        voted_question = Question.objects.create(
            author=self.student,
            title="Voted question",
            description="This receives reputation.",
        )
        cast_vote(
            voter=self.other_user,
            question_id=voted_question.pk,
            value=1,
        )

        response = APIClient().get(f"/api/v1/users/{self.student.pk}/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["contributions"],
            {
                "questions_asked": 2,
                "answers_posted": 1,
                "accepted_answers": 1,
                "comments_posted": 1,
            },
        )
        self.assertEqual(response.json()["reputation"]["reputation"], 5)
        self.assertEqual(response.json()["reputation"]["event_count"], 1)
