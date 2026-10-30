from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .validators import validate_safe_metadata


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    action = models.CharField(max_length=150)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="targeted_audit_events",
        null=True,
        blank=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, validators=[validate_safe_metadata])

    class Meta:
        ordering = ("-timestamp",)

    def clean(self):
        super().clean()
        validate_safe_metadata(self.metadata)

    def save(self, *args, **kwargs):
        validate_safe_metadata(self.metadata)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action} by {self.actor_id} at {self.timestamp}"
