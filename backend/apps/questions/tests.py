from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from .models import Answer, Comment, Question, Tag


class ContentAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Strong-Content-Passphrase-52!"
        cls.author = User.objects.create_user("author@gvpcew.ac.in", cls.password)
        cls.other_user = User.objects.create_user("other@gvpcew.ac.in", cls.password)
        cls.administrator = User.objects.create_superuser(
            "admin@gvpcew.ac.in", cls.password
        )

    def setUp(self):
        self.author_client = self.client_for(self.author)
        self.other_client = self.client_for(self.other_user)
        self.admin_client = self.client_for(self.administrator)

    def client_for(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        csrf_response = client.get("/api/v1/auth/csrf/")
        self.assertEqual(csrf_response.status_code, 200)
        client.csrf_token = csrf_response.json()["csrf_token"]
        return client

    def post(self, client, url, data):
        return client.post(
            url,
            data,
            format="json",
            HTTP_X_CSRFTOKEN=client.csrf_token,
        )

    def patch(self, client, url, data):
        return client.patch(
            url,
            data,
            format="json",
            HTTP_X_CSRFTOKEN=client.csrf_token,
        )

    def delete(self, client, url):
        return client.delete(url, HTTP_X_CSRFTOKEN=client.csrf_token)

    def create_question(self, client=None, **overrides):
        client = client or self.author_client
        payload = {
            "title": "How do I use Django models?",
            "description": "I need help understanding model relationships.",
            **overrides,
        }
        response = self.post(client, "/api/v1/questions/", payload)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def create_tag(self, name="python", client=None, **extras):
        client = client or self.admin_client
        response = self.post(client, "/api/v1/tags/", {"name": name, **extras})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_question_create_list_retrieve_and_author_cannot_be_overridden(self):
        question = self.create_question(
            author=self.other_user.pk,
            status="CLOSED",
        )
        saved = Question.objects.get(pk=question["id"])
        self.assertEqual(saved.author, self.author)
        self.assertEqual(saved.status, Question.Status.CLOSED)

        listing = self.author_client.get("/api/v1/questions/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(listing.json()["results"][0]["author"]["id"], self.author.pk)

        detail = self.other_client.get(f"/api/v1/questions/{saved.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["description"], saved.description)

    def test_anonymous_user_cannot_create_question(self):
        client = APIClient(enforce_csrf_checks=True)

        response = client.post(
            "/api/v1/questions/",
            {"title": "Anonymous", "description": "Should be denied."},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Question.objects.count(), 0)

    def test_anonymous_users_cannot_write_answers_comments_or_tags(self):
        question = self.create_question()
        client = APIClient(enforce_csrf_checks=True)

        answer = client.post(
            f"/api/v1/questions/{question['id']}/answers/",
            {"body": "Anonymous answer"},
            format="json",
        )
        question_comment = client.post(
            f"/api/v1/questions/{question['id']}/comments/",
            {"content": "Anonymous comment"},
            format="json",
        )
        tag = client.post("/api/v1/tags/", {"name": "anonymous"}, format="json")

        self.assertEqual(answer.status_code, 403)
        self.assertEqual(question_comment.status_code, 403)
        self.assertEqual(tag.status_code, 403)

    def test_only_question_owner_or_administrator_can_edit_or_delete(self):
        question = self.create_question()
        url = f"/api/v1/questions/{question['id']}/"

        self.assertEqual(self.other_client.patch(
            url, {"title": "Hijacked"}, format="json", HTTP_X_CSRFTOKEN=self.other_client.csrf_token
        ).status_code, 403)
        self.assertEqual(self.delete(self.other_client, url).status_code, 403)
        self.assertEqual(self.patch(self.author_client, url, {"title": "Updated title"}).status_code, 200)
        self.assertEqual(self.patch(self.admin_client, url, {"title": "Admin edit"}).status_code, 200)
        self.assertEqual(self.delete(self.admin_client, url).status_code, 204)

    def test_tag_normalization_duplicates_permissions_and_question_filter(self):
        denied = self.post(self.author_client, "/api/v1/tags/", {"name": "Python"})
        self.assertEqual(denied.status_code, 403)

        tag = self.create_tag("  PyThOn   Language ")
        self.assertEqual(tag["name"], "python language")
        self.assertEqual(tag["slug"], "python-language")

        duplicate = self.post(
            self.admin_client,
            "/api/v1/tags/",
            {"name": " PYTHON language "},
        )
        self.assertEqual(duplicate.status_code, 400)

        matching = self.create_question(tags=[tag["slug"]])
        self.create_question(title="A question without the tag")
        filtered = self.author_client.get(
            f"/api/v1/questions/?tag={tag['slug']}"
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual([item["id"] for item in filtered.json()["results"]], [matching["id"]])

        admin_edit = self.patch(
            self.admin_client,
            f"/api/v1/tags/{tag['id']}/",
            {"description": "Administrator-maintained tag."},
        )
        self.assertEqual(admin_edit.status_code, 200)
        ordinary_edit = self.patch(
            self.author_client,
            f"/api/v1/tags/{tag['id']}/",
            {"description": "Unauthorized change."},
        )
        self.assertEqual(ordinary_edit.status_code, 403)

    def test_question_search_ordering_and_pagination(self):
        first = self.create_question(title="First unique subject", description="Searching text alpha")
        second = self.create_question(title="Second unique subject", description="Other text")
        third = self.create_question(title="Third unique subject", description="Other text")
        base_time = timezone.now()
        for offset, item in enumerate((first, second, third)):
            Question.objects.filter(pk=item["id"]).update(
                created_at=base_time + timedelta(seconds=offset)
            )

        page = self.author_client.get("/api/v1/questions/?page_size=1&page=2&ordering=created_at")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["count"], 3)
        self.assertEqual(page.json()["results"][0]["id"], second["id"])

        search = self.author_client.get("/api/v1/questions/?search=alpha")
        self.assertEqual(search.status_code, 200)
        self.assertEqual([item["id"] for item in search.json()["results"]], [first["id"]])

    def test_answers_require_open_question_and_enforce_owner_or_admin(self):
        question = self.create_question()
        answer_url = f"/api/v1/questions/{question['id']}/answers/"
        answer_response = self.post(
            self.other_client,
            answer_url,
            {"body": "A valid answer.", "author": self.author.pk},
        )
        self.assertEqual(answer_response.status_code, 201, answer_response.content)
        answer = Answer.objects.get(pk=answer_response.json()["id"])
        self.assertEqual(answer.author, self.other_user)

        another_answer = self.post(self.other_client, answer_url, {"body": "An alternative answer."})
        self.assertEqual(another_answer.status_code, 201)

        empty = self.post(self.author_client, answer_url, {"body": "  "})
        self.assertEqual(empty.status_code, 400)

        answer_detail = f"/api/v1/answers/{answer.pk}/"
        self.assertEqual(self.author_client.patch(
            answer_detail,
            {"body": "Unauthorized edit"},
            format="json",
            HTTP_X_CSRFTOKEN=self.author_client.csrf_token,
        ).status_code, 403)
        self.assertEqual(self.delete(self.author_client, answer_detail).status_code, 403)
        self.assertEqual(self.patch(self.other_client, answer_detail, {"body": "Owner edit"}).status_code, 200)
        self.assertEqual(self.patch(self.admin_client, answer_detail, {"body": "Admin edit"}).status_code, 200)
        self.assertEqual(self.delete(self.admin_client, answer_detail).status_code, 204)

        self.assertEqual(self.patch(
            self.author_client,
            f"/api/v1/questions/{question['id']}/",
            {"status": "CLOSED"},
        ).status_code, 200)
        closed_answer = self.post(self.author_client, answer_url, {"body": "Too late"})
        self.assertEqual(closed_answer.status_code, 400)

    def test_comments_attach_to_one_existing_target_and_enforce_ownership(self):
        question = self.create_question()
        question_id = question["id"]
        question_comment_response = self.post(
            self.author_client,
            f"/api/v1/questions/{question_id}/comments/",
            {"content": "Question comment."},
        )
        self.assertEqual(question_comment_response.status_code, 201)
        question_comment = Comment.objects.get(pk=question_comment_response.json()["id"])
        self.assertEqual(question_comment.question_id, question_id)
        self.assertIsNone(question_comment.answer_id)

        answer_response = self.post(
            self.other_client,
            f"/api/v1/questions/{question_id}/answers/",
            {"body": "Answer to comment on."},
        )
        answer_id = answer_response.json()["id"]
        answer_comment_response = self.post(
            self.other_client,
            f"/api/v1/answers/{answer_id}/comments/",
            {"content": "Answer comment."},
        )
        self.assertEqual(answer_comment_response.status_code, 201)
        answer_comment = Comment.objects.get(pk=answer_comment_response.json()["id"])
        self.assertEqual(answer_comment.answer_id, answer_id)
        self.assertIsNone(answer_comment.question_id)

        comment_url = f"/api/v1/comments/{question_comment.pk}/"
        self.assertEqual(self.other_client.patch(
            comment_url,
            {"content": "Unauthorized"},
            format="json",
            HTTP_X_CSRFTOKEN=self.other_client.csrf_token,
        ).status_code, 403)
        self.assertEqual(self.delete(self.other_client, comment_url).status_code, 403)
        self.assertEqual(self.patch(self.author_client, comment_url, {"content": "Owner edit"}).status_code, 200)
        self.assertEqual(self.patch(self.admin_client, comment_url, {"content": "Admin edit"}).status_code, 200)
        self.assertEqual(self.delete(self.admin_client, comment_url).status_code, 204)

    def test_generic_comment_creation_rejects_both_or_neither_target(self):
        question = self.create_question()
        answer_response = self.post(
            self.author_client,
            f"/api/v1/questions/{question['id']}/answers/",
            {"body": "Target answer."},
        )
        answer_id = answer_response.json()["id"]

        neither = self.post(self.author_client, "/api/v1/comments/", {"content": "No target"})
        both = self.post(
            self.author_client,
            "/api/v1/comments/",
            {"content": "Two targets", "question": question["id"], "answer": answer_id},
        )
        missing_target = self.post(
            self.author_client,
            "/api/v1/comments/",
            {"content": "Unknown target", "question": 999999},
        )
        self.assertEqual(neither.status_code, 400)
        self.assertEqual(both.status_code, 400)
        self.assertEqual(missing_target.status_code, 400)

    def test_admin_can_override_question_ownership(self):
        question = self.create_question()
        url = f"/api/v1/questions/{question['id']}/"

        updated = self.patch(self.admin_client, url, {"title": "Administrator edit"})

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(Question.objects.get(pk=question["id"]).title, "Administrator edit")
