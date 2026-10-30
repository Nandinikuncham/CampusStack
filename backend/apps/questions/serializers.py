from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.models import User

from .models import Answer, Comment, Question, Tag, Vote, normalize_tag_name
from .services import get_vote_summary


class ContentAuthorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "name", "account_type")

    def get_name(self, obj):
        return " ".join(part for part in (obj.first_name, obj.last_name) if part)


class VoteSummaryMixin:
    def _vote_summary(self, obj):
        if all(hasattr(obj, field) for field in ("upvote_count", "downvote_count", "score")):
            return {
                "upvote_count": obj.upvote_count,
                "downvote_count": obj.downvote_count,
                "score": obj.score,
            }
        cache = getattr(self, "_vote_summary_cache", None)
        if cache is None:
            cache = self._vote_summary_cache = {}
        if obj.pk not in cache:
            cache[obj.pk] = get_vote_summary(obj)
        return cache[obj.pk]

    def get_upvote_count(self, obj):
        return self._vote_summary(obj)["upvote_count"]

    def get_downvote_count(self, obj):
        return self._vote_summary(obj)["downvote_count"]

    def get_score(self, obj):
        return self._vote_summary(obj)["score"]


class TagSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=60, required=False)

    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "description")
        read_only_fields = ("id",)

    def validate(self, attrs):
        name = normalize_tag_name(attrs.get("name", self.instance.name if self.instance else ""))
        slug_value = attrs.get("slug")
        if slug_value is None:
            slug_value = self.instance.slug if self.instance else name
        slug = slugify(slug_value)
        if not name:
            raise serializers.ValidationError({"name": "Tag name cannot be empty."})
        if not slug:
            raise serializers.ValidationError({"slug": "Tag name must produce a valid slug."})

        name_conflicts = Tag.objects.filter(name__iexact=name)
        slug_conflicts = Tag.objects.filter(slug=slug)
        if self.instance:
            name_conflicts = name_conflicts.exclude(pk=self.instance.pk)
            slug_conflicts = slug_conflicts.exclude(pk=self.instance.pk)
        if name_conflicts.exists():
            raise serializers.ValidationError({"name": "A tag with this name already exists."})
        if slug_conflicts.exists():
            raise serializers.ValidationError({"slug": "A tag with this slug already exists."})

        attrs["name"] = name
        attrs["slug"] = slug
        return attrs

    def create(self, validated_data):
        tag = Tag(**validated_data)
        try:
            tag.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        tag.save()
        return tag

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        instance.save()
        return instance


class QuestionSerializer(VoteSummaryMixin, serializers.ModelSerializer):
    upvote_count = serializers.SerializerMethodField()
    downvote_count = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    author = ContentAuthorSerializer(read_only=True)
    tags = serializers.SlugRelatedField(
        many=True,
        slug_field="slug",
        queryset=Tag.objects.all(),
        required=False,
    )
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    description = serializers.CharField(trim_whitespace=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "author",
            "title",
            "description",
            "department",
            "status",
            "tags",
            "upvote_count",
            "downvote_count",
            "score",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "author", "created_at", "updated_at")

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Question title cannot be empty.")
        return value.strip()

    def validate_description(self, value):
        if not value.strip():
            raise serializers.ValidationError("Question description cannot be empty.")
        return value.strip()


class AnswerSerializer(VoteSummaryMixin, serializers.ModelSerializer):
    upvote_count = serializers.SerializerMethodField()
    downvote_count = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    author = ContentAuthorSerializer(read_only=True)
    question = serializers.PrimaryKeyRelatedField(read_only=True)
    body = serializers.CharField(trim_whitespace=True)

    class Meta:
        model = Answer
        fields = (
            "id",
            "question",
            "author",
            "body",
            "is_accepted",
            "upvote_count",
            "downvote_count",
            "score",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "question",
            "author",
            "is_accepted",
            "created_at",
            "updated_at",
        )

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Answer cannot be empty.")
        return value.strip()

    def validate(self, attrs):
        question = self.context.get("question")
        if self.instance is None and question and question.status != Question.Status.OPEN:
            raise serializers.ValidationError(
                {"question": "Answers can only be added to open questions."}
            )
        return attrs


class CommentWriteSerializer(serializers.ModelSerializer):
    question = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all(), required=False, allow_null=True, write_only=True
    )
    answer = serializers.PrimaryKeyRelatedField(
        queryset=Answer.objects.all(), required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = Comment
        fields = ("content", "question", "answer")
        extra_kwargs = {"content": {"trim_whitespace": True}}

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()

    def validate(self, attrs):
        question = attrs.get("question")
        answer = attrs.get("answer")
        fixed_target = self.context.get("fixed_target")

        if fixed_target:
            target_type, target_obj = fixed_target
            if question is not None and answer is not None:
                raise serializers.ValidationError(
                    "A comment must target exactly one question or answer."
                )
            if question is not None and (target_type != "question" or question.pk != target_obj.pk):
                raise serializers.ValidationError({"question": "Target does not match this URL."})
            if answer is not None and (target_type != "answer" or answer.pk != target_obj.pk):
                raise serializers.ValidationError({"answer": "Target does not match this URL."})
            attrs["question"] = target_obj if target_type == "question" else None
            attrs["answer"] = target_obj if target_type == "answer" else None
        elif bool(question) == bool(answer):
            raise serializers.ValidationError(
                "A comment must target exactly one question or answer."
            )
        return attrs

    def create(self, validated_data):
        comment = Comment(**validated_data)
        try:
            comment.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict or exc.messages) from exc
        comment.save()
        return comment


class CommentUpdateSerializer(serializers.ModelSerializer):
    content = serializers.CharField(trim_whitespace=True)

    class Meta:
        model = Comment
        fields = ("content",)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()


class CommentReadSerializer(serializers.ModelSerializer):
    author = ContentAuthorSerializer(read_only=True)
    question = serializers.PrimaryKeyRelatedField(read_only=True)
    answer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "author",
            "content",
            "question",
            "answer",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class VoteInputSerializer(serializers.Serializer):
    value = serializers.ChoiceField(
        choices=((Vote.Value.DOWNVOTE, "Downvote"), (Vote.Value.UPVOTE, "Upvote"))
    )
