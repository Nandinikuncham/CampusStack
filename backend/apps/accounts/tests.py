from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import User


class UserModelTests(TestCase):
    def test_email_is_login_identifier_and_normalized(self):
        user = User.objects.create_user("Student@Example.COM", "correct-horse")

        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertEqual(user.email, "student@example.com")
        self.assertTrue(user.check_password("correct-horse"))
        self.assertNotEqual(user.password, "correct-horse")
        self.assertEqual(user.account_type, User.AccountType.STUDENT)

    def test_invalid_account_type_fails_model_validation(self):
        user = User(email="student@example.com", account_type="UNKNOWN")

        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_regular_user_creation_cannot_grant_admin_role(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                "admin@example.com",
                "not-used",
                account_type=User.AccountType.ADMIN,
            )


class AdministratorPermissionTests(TestCase):
    def test_only_active_admin_account_passes_permission(self):
        from rest_framework.test import APIRequestFactory

        from .permissions import IsCampusAdministrator

        permission = IsCampusAdministrator()
        request = APIRequestFactory().get("/")

        request.user = User(
            email="student@example.com",
            account_type=User.AccountType.STUDENT,
        )
        self.assertFalse(permission.has_permission(request, None))

        request.user = User(
            email="admin@example.com",
            account_type=User.AccountType.ADMIN,
            is_active=True,
        )
        self.assertTrue(permission.has_permission(request, None))

        request.user.is_active = False
        self.assertFalse(permission.has_permission(request, None))
