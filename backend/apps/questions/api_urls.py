from rest_framework.routers import DefaultRouter

from .views import AnswerViewSet, CommentViewSet, QuestionViewSet, TagViewSet


router = DefaultRouter()
router.register("questions", QuestionViewSet, basename="question")
router.register("answers", AnswerViewSet, basename="answer")
router.register("comments", CommentViewSet, basename="comment")
router.register("tags", TagViewSet, basename="tag")

urlpatterns = router.urls
