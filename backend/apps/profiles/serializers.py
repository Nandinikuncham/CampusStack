from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import User
from apps.academics.services import AcademicProgressionError, calculate_academic_status
from apps.questions.services import get_reputation_summary

from .models import FacultyProfile, StudentProfile


class PublicProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    academic_status = serializers.SerializerMethodField()
    batch_start_year = serializers.SerializerMethodField()
    batch_end_year = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()
    biography = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    joined_at = serializers.DateTimeField(source="date_joined", read_only=True)
    contributions = serializers.SerializerMethodField()
    reputation = serializers.SerializerMethodField()
    follower_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "display_name",
            "account_type",
            "department",
            "academic_status",
            "batch_start_year",
            "batch_end_year",
            "designation",
            "biography",
            "profile_image_url",
            "joined_at",
            "contributions",
            "reputation",
            "follower_count",
            "following_count",
        )
        read_only_fields = fields

    def get_display_name(self, obj):
        return " ".join(part for part in (obj.first_name, obj.last_name) if part)

    def _profile(self, obj):
        if obj.account_type == User.AccountType.STUDENT:
            try:
                return obj.student_profile
            except StudentProfile.DoesNotExist:
                return None
        if obj.account_type == User.AccountType.FACULTY:
            try:
                return obj.faculty_profile
            except FacultyProfile.DoesNotExist:
                return None
        return None

    def get_department(self, obj):
        profile = self._profile(obj)
        return profile.department if profile else None

    def get_academic_status(self, obj):
        if obj.account_type != User.AccountType.STUDENT:
            return None
        profile = self._profile(obj)
        if profile is None:
            return None
        try:
            return calculate_academic_status(profile)
        except AcademicProgressionError:
            return None

    def get_batch_start_year(self, obj):
        profile = self._profile(obj)
        return profile.batch_start_year if isinstance(profile, StudentProfile) else None

    def get_batch_end_year(self, obj):
        profile = self._profile(obj)
        return profile.batch_end_year if isinstance(profile, StudentProfile) else None

    def get_designation(self, obj):
        profile = self._profile(obj)
        return profile.designation if isinstance(profile, FacultyProfile) else None

    def get_biography(self, obj):
        profile = self._profile(obj)
        return profile.biography if profile else ""

    def get_profile_image_url(self, obj):
        profile = self._profile(obj)
        return profile.profile_image_url or None if profile else None

    def get_contributions(self, obj):
        return {
            "questions_asked": obj.questions_asked,
            "answers_posted": obj.answers_posted,
            "accepted_answers": obj.accepted_answers,
            "comments_posted": obj.comments_posted,
        }

    def get_reputation(self, obj):
        return get_reputation_summary(obj)


class OwnProfileSerializer(PublicProfileSerializer):
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    biography = serializers.CharField(required=False, allow_blank=True, max_length=500)
    profile_image_url = serializers.URLField(
        required=False, allow_blank=True, max_length=500
    )
    designation = serializers.CharField(required=False, max_length=120, trim_whitespace=True)

    class Meta(PublicProfileSerializer.Meta):
        fields = PublicProfileSerializer.Meta.fields + (
            "email",
            "first_name",
            "last_name",
        )
        read_only_fields = tuple(
            field
            for field in PublicProfileSerializer.Meta.fields
            if field not in {"biography", "profile_image_url"}
        ) + ("email",)

    def get_fields(self):
        fields = super().get_fields()
        user = self.instance
        if user is None or user.account_type != User.AccountType.FACULTY:
            fields.pop("designation", None)
        if user is None or user.account_type == User.AccountType.ADMIN:
            fields.pop("biography", None)
            fields.pop("profile_image_url", None)
        return fields

    def validate(self, attrs):
        user = self.instance
        allowed = {"first_name", "last_name"}
        if user.account_type == User.AccountType.STUDENT:
            allowed.update({"biography", "profile_image_url"})
        elif user.account_type == User.AccountType.FACULTY:
            allowed.update({"biography", "profile_image_url", "designation"})
        unexpected = set(self.initial_data) - allowed
        if unexpected:
            raise serializers.ValidationError(
                {field: "This field cannot be changed through profile editing." for field in unexpected}
            )
        profile_updates = set(attrs) & {"biography", "profile_image_url", "designation"}
        if profile_updates and user.account_type == User.AccountType.STUDENT:
            if not StudentProfile.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {field: "A student profile is required to edit this field." for field in profile_updates}
                )
        elif profile_updates and user.account_type == User.AccountType.FACULTY:
            if not FacultyProfile.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {field: "A faculty profile is required to edit this field." for field in profile_updates}
                )
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_fields = {"biography", "profile_image_url", "designation"}
        profile_updates = {
            field: validated_data.pop(field)
            for field in tuple(validated_data)
            if field in profile_fields
        }
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if profile_updates:
            if instance.account_type == User.AccountType.STUDENT:
                profile = instance.student_profile
            elif instance.account_type == User.AccountType.FACULTY:
                profile = instance.faculty_profile
            else:
                raise serializers.ValidationError("Administrator profiles cannot be edited here.")
            for field, value in profile_updates.items():
                setattr(profile, field, value)
            try:
                profile.full_clean()
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict or exc.messages) from exc
            profile.save(update_fields=tuple(profile_updates))
        return instance
