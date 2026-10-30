from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Create users with normalized email identifiers and safe role defaults."""

    use_in_migrations = True

    @staticmethod
    def _normalize_email(email):
        return BaseUserManager.normalize_email(email.strip()).casefold()

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")

        email = self._normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        from .models import User

        account_type = extra_fields.setdefault("account_type", User.AccountType.STUDENT)
        if account_type == User.AccountType.ADMIN:
            raise ValueError("Administrator accounts cannot be created through create_user().")
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        from .models import User

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("account_type", User.AccountType.ADMIN)
        if not extra_fields["is_staff"]:
            raise ValueError("A superuser must have is_staff=True.")
        if not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have is_superuser=True.")
        if extra_fields["account_type"] != User.AccountType.ADMIN:
            raise ValueError("A superuser must have the ADMIN account type.")
        return self._create_user(email, password, **extra_fields)
