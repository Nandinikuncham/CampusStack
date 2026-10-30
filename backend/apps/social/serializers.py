from rest_framework import serializers

from apps.accounts.models import User
from apps.questions.models import Tag

from .models import Mentorship, MentorshipRequest


class SocialUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "display_name", "account_type")
        read_only_fields = fields

    def get_display_name(self, obj):
        return " ".join(part for part in (obj.first_name, obj.last_name) if part)


class FollowedTagSerializer(serializers.ModelSerializer):
    follower_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "description", "follower_count")
        read_only_fields = fields

    def get_follower_count(self, obj):
        if hasattr(obj, "follower_count"):
            return obj.follower_count
        return obj.social_followers.count()


class MentorshipRequestCreateSerializer(serializers.Serializer):
    mentor_id = serializers.PrimaryKeyRelatedField(
        source="mentor",
        queryset=User.objects.filter(is_active=True),
    )
    message = serializers.CharField(max_length=500, trim_whitespace=True)

    def validate_message(self, value):
        if not value:
            raise serializers.ValidationError("A short purpose message is required.")
        return value

    def validate(self, attrs):
        unexpected = set(self.initial_data) - {"mentor_id", "message"}
        if unexpected:
            raise serializers.ValidationError(
                {field: "This field is controlled by the server." for field in unexpected}
            )
        return attrs


class MentorshipRequestSerializer(serializers.ModelSerializer):
    student = SocialUserSerializer(read_only=True)
    mentor = SocialUserSerializer(read_only=True)

    class Meta:
        model = MentorshipRequest
        fields = (
            "id",
            "student",
            "mentor",
            "message",
            "status",
            "created_at",
            "updated_at",
            "resolved_at",
        )
        read_only_fields = fields


class MentorshipSerializer(serializers.ModelSerializer):
    student = SocialUserSerializer(read_only=True)
    mentor = SocialUserSerializer(read_only=True)

    class Meta:
        model = Mentorship
        fields = ("id", "student", "mentor", "status", "started_at", "completed_at")
        read_only_fields = fields
