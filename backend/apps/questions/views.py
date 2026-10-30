from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsCampusAdministrator

from .models import Answer, Comment, Question, Tag
from .pagination import ContentPagination
from .permissions import IsAuthorOrCampusAdministrator
from .serializers import (
    AnswerSerializer,
    CommentReadSerializer,
    CommentUpdateSerializer,
    CommentWriteSerializer,
    QuestionSerializer,
    TagSerializer,
)


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.select_related("author").prefetch_related("tags")
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContentPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsAuthorOrCampusAdministrator()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        tag_slug = self.request.query_params.get("tag")
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)
        return queryset.distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["get", "post"], url_path="answers")
    def answers(self, request, pk=None):
        question = self.get_object()
        if request.method == "GET":
            answers = question.answers.select_related("author")
            page = self.paginate_queryset(answers)
            if page is not None:
                return self.get_paginated_response(AnswerSerializer(page, many=True).data)
            return Response(AnswerSerializer(answers, many=True).data)

        with transaction.atomic():
            question = get_object_or_404(
                Question.objects.select_for_update(), pk=question.pk
            )
            if question.status != Question.Status.OPEN:
                raise serializers.ValidationError(
                    {"question": "Answers can only be added to open questions."}
                )
            serializer = AnswerSerializer(
                data=request.data,
                context={"request": request, "question": question},
            )
            serializer.is_valid(raise_exception=True)
            answer = serializer.save(question=question, author=request.user)
        return Response(
            AnswerSerializer(answer).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        question = self.get_object()
        if request.method == "GET":
            comments = question.comments.select_related("author")
            page = self.paginate_queryset(comments)
            if page is not None:
                data = CommentReadSerializer(page, many=True).data
                return self.get_paginated_response(data)
            return Response(CommentReadSerializer(comments, many=True).data)

        serializer = CommentWriteSerializer(
            data=request.data,
            context={"request": request, "fixed_target": ("question", question)},
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(author=request.user)
        return Response(
            CommentReadSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )


class AnswerViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Answer.objects.select_related("author", "question")
    serializer_class = AnswerSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsAuthorOrCampusAdministrator()]
        return super().get_permissions()

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        answer = self.get_object()
        if request.method == "GET":
            comments = answer.comments.select_related("author")
            page = self.paginate_queryset(comments)
            if page is not None:
                return self.get_paginated_response(
                    CommentReadSerializer(page, many=True).data
                )
            return Response(CommentReadSerializer(comments, many=True).data)

        serializer = CommentWriteSerializer(
            data=request.data,
            context={"request": request, "fixed_target": ("answer", answer)},
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(author=request.user)
        return Response(
            CommentReadSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.select_related("author", "question", "answer")
    permission_classes = [IsAuthenticated]
    pagination_class = ContentPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsAuthorOrCampusAdministrator()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return CommentWriteSerializer
        if self.action in {"update", "partial_update"}:
            return CommentUpdateSerializer
        return CommentReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(author=request.user)
        return Response(
            CommentReadSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContentPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsCampusAdministrator()]
        return super().get_permissions()
