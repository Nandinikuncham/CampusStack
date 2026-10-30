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
    is_accepted = models.BooleanField(default=False)
    acceptance_revision = models.PositiveIntegerField(default=0)
    acceptance_event = models.ForeignKey(
        "ReputationEvent",
        on_delete=models.SET_NULL,
        related_name="accepted_answer_for",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(body=""),
                name="questions_answer_body_nonempty",
            ),
            models.UniqueConstraint(
                fields=("question",),
                condition=Q(is_accepted=True),
                name="questions_one_accepted_per_question",
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


class Vote(models.Model):
    class Value(models.IntegerChoices):
        DOWNVOTE = -1, "Downvote"
        UPVOTE = 1, "Upvote"

    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_votes",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="votes",
        null=True,
        blank=True,
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name="votes",
        null=True,
        blank=True,
    )
    value = models.SmallIntegerField(choices=Value.choices)
    is_active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    reputation_event = models.ForeignKey(
        "ReputationEvent",
        on_delete=models.SET_NULL,
        related_name="current_for_votes",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(question__isnull=False, answer__isnull=True)
                    | Q(question__isnull=True, answer__isnull=False)
                ),
                name="questions_vote_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=Q(value__in=(-1, 1)),
                name="questions_vote_value_valid",
            ),
            models.UniqueConstraint(
                fields=("voter", "question"),
                condition=Q(question__isnull=False),
                name="questions_one_vote_per_question_user",
            ),
            models.UniqueConstraint(
                fields=("voter", "answer"),
                condition=Q(answer__isnull=False),
                name="questions_one_vote_per_answer_user",
            ),
        ]
        indexes = [
            models.Index(fields=("question", "is_active", "value"), name="votes_question_active_idx"),
            models.Index(fields=("answer", "is_active", "value"), name="votes_answer_active_idx"),
        ]

    def clean(self):
        super().clean()
        if bool(self.question_id) == bool(self.answer_id):
            raise ValidationError("A vote must target exactly one question or answer.")
        if self.value not in self.Value.values:
            raise ValidationError({"value": "Vote must be an upvote or downvote."})
        target_author_id = (
            self.question.author_id if self.question_id else self.answer.author_id
        )
        if self.voter_id and self.voter_id == target_author_id:
            raise ValidationError("Users cannot vote on their own content.")

    def __str__(self):
        return f"Vote {self.value} by {self.voter_id}"


class ReputationEvent(models.Model):
    class EventType(models.TextChoices):
        QUESTION_UPVOTE = "QUESTION_UPVOTE", "Question upvote"
        QUESTION_DOWNVOTE = "QUESTION_DOWNVOTE", "Question downvote"
        ANSWER_UPVOTE = "ANSWER_UPVOTE", "Answer upvote"
        ANSWER_DOWNVOTE = "ANSWER_DOWNVOTE", "Answer downvote"
        ANSWER_ACCEPTED = "ANSWER_ACCEPTED", "Accepted answer"
        REVERSAL = "REVERSAL", "Reversal"

    class SourceType(models.TextChoices):
        VOTE = "VOTE", "Vote"
        ANSWER_ACCEPTANCE = "ANSWER_ACCEPTANCE", "Answer acceptance"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reputation_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reputation_actions",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    delta = models.IntegerField()
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_id = models.PositiveBigIntegerField()
    idempotency_key = models.CharField(max_length=128, unique=True)
    reverses = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reversal_events",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="questions_reputation_delta_nonzero"),
            models.CheckConstraint(
                condition=(
                    Q(event_type="REVERSAL", reverses__isnull=False)
                    | (~Q(event_type="REVERSAL") & Q(reverses__isnull=True))
                ),
                name="questions_reputation_reversal_consistent",
            ),
            models.UniqueConstraint(
                fields=("reverses",),
                condition=Q(reverses__isnull=False),
                name="questions_reputation_one_reversal",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "created_at"), name="reputation_user_date_idx"),
        ]

    def clean(self):
        super().clean()
        if self.event_type == self.EventType.REVERSAL:
            if not self.reverses_id:
                raise ValidationError({"reverses": "A reversal must reference its original event."})
            if self.reverses.event_type == self.EventType.REVERSAL:
                raise ValidationError({"reverses": "A reversal cannot reverse another reversal."})
            if self.delta != -self.reverses.delta or self.user_id != self.reverses.user_id:
                raise ValidationError("Reversal must exactly compensate its original event.")
        elif self.reverses_id:
            raise ValidationError({"reverses": "Only reversal events may reference another event."})

    def __str__(self):
        return f"{self.event_type} {self.delta:+d} for user {self.user_id}"


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
