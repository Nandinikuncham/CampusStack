from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User

from .models import AuditEvent


class AuditEventTests(TestCase):
    def test_metadata_rejects_credential_fields(self):
        actor = User.objects.create_user("student@example.com", "pw")

        with self.assertRaises(ValidationError):
            AuditEvent.objects.create(
                actor=actor,
                action="test",
                metadata={"nested": {"access_token": "should-not-be-stored"}},
            )
