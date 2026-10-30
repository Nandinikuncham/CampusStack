from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .managers import UserManager


class User(AbstractUser):
    class AccountType(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        FACULTY = "FACULTY", "Faculty"
        ADMIN = "ADMIN", "Administrator"

    username = None
    email = models.EmailField(unique=True)
    account_type = models.CharField(
        max_length=10,
        choices=AccountType.choices,
        default=AccountType.STUDENT,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(account_type__in=("STUDENT", "FACULTY", "ADMIN")),
                name="accounts_user_valid_account_type",
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = UserManager._normalize_email(self.email)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = UserManager._normalize_email(self.email)
        if self.account_type not in self.AccountType.values:
            raise ValidationError({"account_type": "Select a valid account type."})
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.email
