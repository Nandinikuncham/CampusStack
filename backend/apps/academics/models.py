from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class AcademicCalendar(models.Model):
    academic_year = models.CharField(max_length=20, unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ("starts_on",)
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__gt=F("starts_on")),
                name="academics_calendar_end_after_start",
            ),
            models.UniqueConstraint(
                fields=("is_current",),
                condition=Q(is_current=True),
                name="academics_only_one_current_calendar",
            ),
        ]

    def clean(self):
        super().clean()
        if self.starts_on and self.ends_on and self.ends_on <= self.starts_on:
            raise ValidationError({"ends_on": "Academic year must end after it starts."})

    def __str__(self):
        return self.academic_year
