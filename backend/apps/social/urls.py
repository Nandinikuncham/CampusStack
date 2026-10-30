from django.urls import path

from .views import (
    ActiveMentorshipsView,
    ApproveMentorshipRequestView,
    CancelMentorshipRequestView,
    CompleteMentorshipView,
    FollowersView,
    FollowingView,
    FollowedTagsView,
    MentorshipRequestCreateView,
    ReceivedMentorshipRequestsView,
    RejectMentorshipRequestView,
    SentMentorshipRequestsView,
    TagFollowView,
    UserFollowView,
)


app_name = "social"

urlpatterns = [
    path("users/<int:user_id>/follow/", UserFollowView.as_view(), name="user-follow"),
    path("users/<int:user_id>/followers/", FollowersView.as_view(), name="followers"),
    path("users/<int:user_id>/following/", FollowingView.as_view(), name="following"),
    path("tags/followed/", FollowedTagsView.as_view(), name="followed-tags"),
    path("tags/<int:tag_id>/follow/", TagFollowView.as_view(), name="tag-follow"),
    path("mentorship/requests/", MentorshipRequestCreateView.as_view(), name="mentorship-request-create"),
    path("mentorship/requests/sent/", SentMentorshipRequestsView.as_view(), name="mentorship-request-sent"),
    path("mentorship/requests/received/", ReceivedMentorshipRequestsView.as_view(), name="mentorship-request-received"),
    path("mentorship/requests/<int:request_id>/approve/", ApproveMentorshipRequestView.as_view(), name="mentorship-request-approve"),
    path("mentorship/requests/<int:request_id>/reject/", RejectMentorshipRequestView.as_view(), name="mentorship-request-reject"),
    path("mentorship/requests/<int:request_id>/cancel/", CancelMentorshipRequestView.as_view(), name="mentorship-request-cancel"),
    path("mentorship/relationships/", ActiveMentorshipsView.as_view(), name="mentorship-relationships"),
    path("mentorship/relationships/<int:mentorship_id>/complete/", CompleteMentorshipView.as_view(), name="mentorship-complete"),
]
