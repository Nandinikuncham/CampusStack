from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.questions.models import Tag
from apps.questions.pagination import ContentPagination

from .models import Mentorship, MentorshipRequest
from .serializers import (
    FollowedTagSerializer,
    MentorshipRequestCreateSerializer,
    MentorshipRequestSerializer,
    MentorshipSerializer,
    SocialUserSerializer,
)
from .services import (
    complete_mentorship,
    create_mentorship_request,
    follow_tag,
    follow_user,
    transition_mentorship_request,
    unfollow_tag,
    unfollow_user,
)


def _service_validation_error(exc):
    raise serializers.ValidationError(
        getattr(exc, "message_dict", None) or exc.messages
    ) from exc


class UserFollowView(APIView):
    permission_classes = [IsAuthenticated]

    def _change(self, request, user_id, should_follow):
        target = get_object_or_404(User, pk=user_id)
        try:
            if should_follow:
                follow_user(follower=request.user, target=target)
            else:
                unfollow_user(follower=request.user, target=target)
        except DjangoValidationError as exc:
            _service_validation_error(exc)
        return Response(
            {
                "is_following": should_follow,
                "follower_count": target.follower_edges.count(),
                "following_count": target.following_edges.count(),
            }
        )

    def post(self, request, user_id):
        return self._change(request, user_id, True)

    def delete(self, request, user_id):
        return self._change(request, user_id, False)


class UserRelationListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = SocialUserSerializer
    pagination_class = ContentPagination
    relation = None

    def get_queryset(self):
        target = get_object_or_404(User, pk=self.kwargs["user_id"])
        if self.relation == "followers":
            return User.objects.filter(following_edges__following=target).order_by(
                "-following_edges__created_at"
            )
        return User.objects.filter(follower_edges__follower=target).order_by(
            "-follower_edges__created_at"
        )


class FollowersView(UserRelationListView):
    relation = "followers"


class FollowingView(UserRelationListView):
    relation = "following"


class TagFollowView(APIView):
    permission_classes = [IsAuthenticated]

    def _change(self, request, tag_id, should_follow):
        tag = get_object_or_404(Tag, pk=tag_id)
        if should_follow:
            follow_tag(user=request.user, tag=tag)
        else:
            unfollow_tag(user=request.user, tag=tag)
        return Response(
            {
                "is_following": should_follow,
                "follower_count": tag.social_followers.count(),
            }
        )

    def post(self, request, tag_id):
        return self._change(request, tag_id, True)

    def delete(self, request, tag_id):
        return self._change(request, tag_id, False)


class FollowedTagsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FollowedTagSerializer
    pagination_class = ContentPagination

    def get_queryset(self):
        return Tag.objects.filter(social_followers__user=self.request.user).annotate(
            follower_count=Count("social_followers", distinct=True)
        ).order_by("name", "pk")


class MentorshipRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MentorshipRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            mentorship_request = create_mentorship_request(
                student=request.user,
                mentor=serializer.validated_data["mentor"],
                message=serializer.validated_data["message"],
            )
        except DjangoValidationError as exc:
            _service_validation_error(exc)
        return Response(
            MentorshipRequestSerializer(mentorship_request).data,
            status=status.HTTP_201_CREATED,
        )


class MentorshipRequestListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MentorshipRequestSerializer
    pagination_class = ContentPagination
    direction = None

    def get_queryset(self):
        if self.direction == "sent":
            return MentorshipRequest.objects.filter(student=self.request.user).select_related(
                "student", "mentor"
            )
        return MentorshipRequest.objects.filter(mentor=self.request.user).select_related(
            "student", "mentor"
        )


class SentMentorshipRequestsView(MentorshipRequestListView):
    direction = "sent"


class ReceivedMentorshipRequestsView(MentorshipRequestListView):
    direction = "received"


class MentorshipRequestTransitionView(APIView):
    permission_classes = [IsAuthenticated]
    transition = None

    def post(self, request, request_id):
        mentorship_request = get_object_or_404(
            MentorshipRequest.objects.filter(
                Q(student=request.user) | Q(mentor=request.user)
            ),
            pk=request_id,
        )
        try:
            mentorship_request = transition_mentorship_request(
                request_id=mentorship_request.pk,
                actor=request.user,
                action=self.transition,
            )
        except DjangoValidationError as exc:
            _service_validation_error(exc)
        return Response(MentorshipRequestSerializer(mentorship_request).data)


class ApproveMentorshipRequestView(MentorshipRequestTransitionView):
    transition = "approve"


class RejectMentorshipRequestView(MentorshipRequestTransitionView):
    transition = "reject"


class CancelMentorshipRequestView(MentorshipRequestTransitionView):
    transition = "cancel"


class ActiveMentorshipsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MentorshipSerializer
    pagination_class = ContentPagination

    def get_queryset(self):
        student_relationships = Mentorship.objects.filter(
            student_id=self.request.user.pk,
            status=Mentorship.Status.ACTIVE,
        ).values("pk")
        mentor_relationships = Mentorship.objects.filter(
            mentor_id=self.request.user.pk,
            status=Mentorship.Status.ACTIVE,
        ).values("pk")
        visible_relationships = student_relationships.union(mentor_relationships)
        return Mentorship.objects.filter(pk__in=visible_relationships).select_related(
            "student", "mentor", "request"
        )


class CompleteMentorshipView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, mentorship_id):
        mentorship = get_object_or_404(
            Mentorship.objects.filter(
                Q(student=request.user) | Q(mentor=request.user)
            ),
            pk=mentorship_id,
        )
        try:
            mentorship = complete_mentorship(
                mentorship_id=mentorship.pk,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            _service_validation_error(exc)
        return Response(MentorshipSerializer(mentorship).data)
