from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


def normalize_tag_name(value):
    return " ".join(value.split()).casefold()


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def clean(self):
        super().clean()
        if self.name:
            self.name = normalize_tag_name(self.name)
        self.slug = slugify(self.slug or self.name)
        if not self.name:
            raise ValidationError({"name": "Tag name cannot be empty."})
        if not self.slug:
            raise ValidationError({"slug": "Tag name must produce a valid slug."})

    def save(self, *args, **kwargs):
        self.name = normalize_tag_name(self.name)
        self.slug = slugify(self.slug or self.name)
        if not self.name or not self.slug:
            raise ValidationError("Tag name and slug must not be empty.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Question(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    department = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.OPEN)
    tags = models.ManyToManyField(Tag, blank=True, related_name="questions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=("OPEN", "CLOSED")),
                name="questions_status_is_valid",
            ),
            models.CheckConstraint(
                condition=~Q(title="") & ~Q(description=""),
                name="questions_title_description_nonempty",
            ),
        ]
        indexes = [
            models.Index(fields=("-created_at",), name="questions_created_idx"),
            models.Index(fields=("author", "-created_at"), name="questions_author_date_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if not self.title or not self.title.strip():
            errors["title"] = "Question title cannot be empty."
        if not self.description or not self.description.strip():
            errors["description"] = "Question description cannot be empty."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(body=""),
                name="questions_answer_body_nonempty",
            ),
        ]
        indexes = [
            models.Index(fields=("question", "created_at"), name="answers_question_date_idx"),
            models.Index(fields=("author", "created_at"), name="answers_author_date_idx"),
        ]

    def clean(self):
        super().clean()
        if not self.body or not self.body.strip():
            raise ValidationError({"body": "Answer cannot be empty."})
        if self._state.adding and self.question_id:
            if self.question.status != Question.Status.OPEN:
                raise ValidationError({"question": "Answers can only be added to open questions."})

    def __str__(self):
        return f"Answer {self.pk} to question {self.question_id}"


class Comment(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_comments",
    )
    content = models.TextField()
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="comments",
        null=True,
        blank=True,
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name="comments",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(question__isnull=False, answer__isnull=True)
                    | Q(question__isnull=True, answer__isnull=False)
                ),
                name="questions_comment_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=~Q(content=""),
                name="questions_comment_content_nonempty",
            ),
        ]
        indexes = [
            models.Index(fields=("question", "created_at"), name="comments_question_date_idx"),
            models.Index(fields=("answer", "created_at"), name="comments_answer_date_idx"),
        ]

    def clean(self):
        super().clean()
        if bool(self.question_id) == bool(self.answer_id):
            raise ValidationError("A comment must belong to exactly one question or answer.")
        if not self.content or not self.content.strip():
            raise ValidationError({"content": "Comment cannot be empty."})

    def __str__(self):
        return f"Comment {self.pk} by {self.author_id}"
