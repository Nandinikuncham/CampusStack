from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.profiles.models import FacultyProfile


class AuthenticationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.student_payload = {
            "name": "Riya Student",
            "email": "riya@gvpcew.ac.in",
            "password": "Strong-Student-Passphrase-74!",
            "department": "Computer Science",
            "batch_start_year": 2024,
            "batch_end_year": 2028,
            "admission_date": "2024-08-01",
            "expected_graduation_date": "2028-06-30",
        }

    def csrf_token(self):
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def post_with_csrf(self, url, data):
        token = self.csrf_token()
        return self.client.post(url, data, format="json", HTTP_X_CSRFTOKEN=token)

    def test_student_registration_is_atomic_safe_and_assigns_student_role(self):
        payload = {**self.student_payload, "account_type": "ADMIN"}
        response = self.post_with_csrf("/api/v1/auth/register/student/", payload)

        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(email=self.student_payload["email"])
        self.assertEqual(user.account_type, User.AccountType.STUDENT)
        self.assertTrue(user.check_password(self.student_payload["password"]))
        self.assertEqual(user.student_profile.department, "Computer Science")
        self.assertNotIn("password", response.json()["user"])
        self.assertNotIn("password_hash", response.json()["user"])

    def test_student_registration_rejects_non_college_domain(self):
        payload = {**self.student_payload, "email": "riya@example.com"}

        response = self.post_with_csrf("/api/v1/auth/register/student/", payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())
        self.assertEqual(User.objects.count(), 0)

    def test_registration_rejects_duplicate_email(self):
        User.objects.create_user(self.student_payload["email"], "existing-password")

        response = self.post_with_csrf(
            "/api/v1/auth/register/student/", self.student_payload
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())
        self.assertEqual(User.objects.count(), 1)

    def test_registration_rejects_invalid_batch_dates(self):
        payload = {
            **self.student_payload,
            "batch_end_year": 2023,
            "expected_graduation_date": "2024-07-31",
        }

        response = self.post_with_csrf("/api/v1/auth/register/student/", payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_student_registration_requires_csrf(self):
        response = self.client.post(
            "/api/v1/auth/register/student/", self.student_payload, format="json"
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "CSRF verification failed."})
        self.assertEqual(User.objects.count(), 0)

    def test_faculty_registration_is_pending_and_ignores_self_approval_fields(self):
        payload = {
            "name": "Dr Faculty",
            "email": "faculty@gvpcew.ac.in",
            "password": "Strong-Faculty-Passphrase-91!",
            "department": "Physics",
            "designation": "Assistant Professor",
            "approval_status": "APPROVED",
            "approved_by": 1,
        }

        response = self.post_with_csrf("/api/v1/auth/register/faculty/", payload)

        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(email=payload["email"])
        self.assertEqual(user.account_type, User.AccountType.FACULTY)
        self.assertEqual(
            user.faculty_profile.approval_status,
            FacultyProfile.ApprovalStatus.PENDING,
        )
        self.assertIsNone(user.faculty_profile.approved_by)
        self.assertIsNone(user.faculty_profile.approved_at)
        self.assertEqual(
            response.json()["user"]["profile"]["approval_status"], "PENDING"
        )

    def test_login_logout_and_me_use_session_authentication(self):
        registration = self.post_with_csrf(
            "/api/v1/auth/register/student/", self.student_payload
        )
        self.assertEqual(registration.status_code, 201)

        login_response = self.post_with_csrf(
            "/api/v1/auth/login/",
            {
                "email": self.student_payload["email"],
                "password": self.student_payload["password"],
            },
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["user"]["account_type"], "STUDENT")

        me_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["user"]["email"], self.student_payload["email"])

        csrf_rejected = self.client.post("/api/v1/auth/logout/", {}, format="json")
        self.assertEqual(csrf_rejected.status_code, 403)

        logout_token = self.csrf_token()
        logout_response = self.client.post(
            "/api/v1/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=logout_token
        )
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 403)

    def test_invalid_login_has_same_message_for_unknown_email_and_wrong_password(self):
        User.objects.create_user("known@gvpcew.ac.in", "a-correct-password-82!")
        token = self.csrf_token()
        unknown = self.client.post(
            "/api/v1/auth/login/",
            {"email": "unknown@gvpcew.ac.in", "password": "wrong-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        wrong_password = self.client.post(
            "/api/v1/auth/login/",
            {"email": "known@gvpcew.ac.in", "password": "wrong-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(wrong_password.status_code, 400)
        self.assertEqual(unknown.json(), wrong_password.json())
        self.assertEqual(unknown.json(), {"detail": "Invalid email or password."})

    def test_login_requires_csrf(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "nobody@gvpcew.ac.in", "password": "unknown"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_cannot_access_me(self):
        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 403)


class ApprovedFacultyPermissionTests(TestCase):
    def test_pending_and_rejected_faculty_are_denied(self):
        from rest_framework.test import APIRequestFactory

        from apps.accounts.permissions import IsApprovedFaculty

        faculty = User.objects.create_user(
            "faculty@gvpcew.ac.in",
            "Strong-Faculty-Passphrase-91!",
            account_type=User.AccountType.FACULTY,
        )
        profile = FacultyProfile.objects.create(
            user=faculty,
            department="Physics",
            designation="Lecturer",
        )
        request = APIRequestFactory().get("/")
        request.user = faculty
        permission = IsApprovedFaculty()

        self.assertFalse(permission.has_permission(request, None))
        profile.approval_status = FacultyProfile.ApprovalStatus.REJECTED
        profile.save(update_fields=("approval_status",))
        self.assertFalse(permission.has_permission(request, None))

        from django.utils import timezone

        administrator = User.objects.create_superuser(
            "admin@gvpcew.ac.in", "Strong-Admin-Passphrase-38!"
        )
        profile.approval_status = FacultyProfile.ApprovalStatus.APPROVED
        profile.approved_by = administrator
        profile.approved_at = timezone.now()
        profile.save(update_fields=("approval_status", "approved_by", "approved_at"))
        self.assertTrue(permission.has_permission(request, None))


class AdministratorProvisioningTests(TestCase):
    def test_django_superuser_creation_assigns_admin_role(self):
        administrator = User.objects.create_superuser(
            "bootstrap@gvpcew.ac.in", "Strong-Admin-Passphrase-38!"
        )

        self.assertEqual(administrator.account_type, User.AccountType.ADMIN)
        self.assertTrue(administrator.is_staff)
        self.assertTrue(administrator.is_superuser)
        self.assertTrue(administrator.check_password("Strong-Admin-Passphrase-38!"))
