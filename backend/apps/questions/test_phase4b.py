from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User

from .models import Answer, Question, ReputationEvent, Vote
from .services import (
    create_reputation_event,
    get_reputation_summary,
    reverse_reputation_event,
    set_accepted_answer,
)


class Phase4BTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Strong-Phase4B-Passphrase-41!"
        cls.question_author = User.objects.create_user("q-author@gvpcew.ac.in", cls.password)
        cls.answer_author = User.objects.create_user("a-author@gvpcew.ac.in", cls.password)
        cls.voter = User.objects.create_user("voter@gvpcew.ac.in", cls.password)
        cls.second_voter = User.objects.create_user("voter2@gvpcew.ac.in", cls.password)
        cls.other_user = User.objects.create_user("other@gvpcew.ac.in", cls.password)

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

    def delete(self, client, url):
        return client.delete(url, HTTP_X_CSRFTOKEN=client.csrf_token)

    def make_question(self, author=None):
        return Question.objects.create(
            author=author or self.question_author,
            title="Question for Phase 4B",
            description="A sufficiently detailed test question.",
        )

    def make_answer(self, question, author=None, body="A useful answer."):
        return Answer.objects.create(
            question=question,
            author=author or self.answer_author,
            body=body,
        )

    def test_question_vote_change_and_removal_reverse_reputation(self):
        question = self.make_question()
        client = self.client_for(self.voter)
        url = f"/api/v1/questions/{question.pk}/vote/"

        upvote = self.post(client, url, {"value": 1})
        self.assertEqual(upvote.status_code, 200, upvote.content)
        self.assertEqual(upvote.json()["score"], 1)
        self.assertEqual(upvote.json()["upvote_count"], 1)
        self.assertEqual(get_reputation_summary(self.question_author)["reputation"], 5)

        repeated = self.post(client, url, {"value": 1})
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(Vote.objects.filter(question=question, voter=self.voter).count(), 1)
        self.assertEqual(ReputationEvent.objects.filter(user=self.question_author).count(), 1)

        changed = self.post(client, url, {"value": -1})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()["score"], -1)
        self.assertEqual(changed.json()["downvote_count"], 1)
        self.assertEqual(get_reputation_summary(self.question_author)["reputation"], -2)

        removed = self.delete(client, url)
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(removed.json()["vote"])
        self.assertEqual(removed.json()["score"], 0)
        self.assertEqual(get_reputation_summary(self.question_author)["reputation"], 0)
        self.assertEqual(ReputationEvent.objects.filter(user=self.question_author).count(), 4)
        self.assertEqual(Vote.objects.get(question=question, voter=self.voter).is_active, False)

    def test_answer_votes_expose_counts_and_award_answer_author(self):
        question = self.make_question()
        answer = self.make_answer(question)
        voter_client = self.client_for(self.voter)
        second_voter_client = self.client_for(self.second_voter)
        vote_url = f"/api/v1/answers/{answer.pk}/vote/"

        self.assertEqual(self.post(voter_client, vote_url, {"value": 1}).status_code, 200)
        downvote = self.post(second_voter_client, vote_url, {"value": -1})
        self.assertEqual(downvote.status_code, 200)
        self.assertEqual(downvote.json()["score"], 0)
        self.assertEqual(get_reputation_summary(self.answer_author)["reputation"], 8)

        detail = voter_client.get(f"/api/v1/answers/{answer.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["upvote_count"], 1)
        self.assertEqual(detail.json()["downvote_count"], 1)
        self.assertEqual(detail.json()["score"], 0)

    def test_self_voting_and_anonymous_voting_are_rejected(self):
        question = self.make_question()
        answer = self.make_answer(question)
        owner = self.client_for(self.question_author)
        anonymous = APIClient(enforce_csrf_checks=True)

        self.assertEqual(
            self.post(owner, f"/api/v1/questions/{question.pk}/vote/", {"value": 1}).status_code,
            403,
        )
        self.assertEqual(
            self.post(owner, f"/api/v1/answers/{answer.pk}/vote/", {"value": 1}).status_code,
            200,
        )
        answer_owner = self.client_for(self.answer_author)
        self.assertEqual(
            self.post(answer_owner, f"/api/v1/answers/{answer.pk}/vote/", {"value": 1}).status_code,
            403,
        )
        self.assertEqual(
            anonymous.post(
                f"/api/v1/questions/{question.pk}/vote/", {"value": 1}, format="json"
            ).status_code,
            403,
        )

    def test_vote_uniqueness_is_enforced_by_database(self):
        question = self.make_question()
        self.post(self.client_for(self.voter), f"/api/v1/questions/{question.pk}/vote/", {"value": 1})

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(voter=self.voter, question=question, value=Vote.Value.DOWNVOTE)

    def test_vote_model_rejects_both_or_neither_target(self):
        question = self.make_question()
        answer = self.make_answer(question)
        with self.assertRaises(Exception):
            Vote(voter=self.voter, value=Vote.Value.UPVOTE).full_clean()
        with self.assertRaises(Exception):
            Vote(
                voter=self.voter,
                question=question,
                answer=answer,
                value=Vote.Value.UPVOTE,
            ).full_clean()

    def test_only_question_author_can_accept_and_replacement_reverses_prior_reward(self):
        question = self.make_question()
        first = self.make_answer(question, author=self.answer_author, body="First answer.")
        second = self.make_answer(question, author=self.other_user, body="Second answer.")
        first_url = f"/api/v1/questions/{question.pk}/answers/{first.pk}/accept/"
        second_url = f"/api/v1/questions/{question.pk}/answers/{second.pk}/accept/"

        unauthorized = self.post(self.client_for(self.voter), first_url, {})
        self.assertEqual(unauthorized.status_code, 403)

        accepted = self.post(self.client_for(self.question_author), first_url, {})
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertTrue(accepted.json()["is_accepted"])
        self.assertEqual(get_reputation_summary(self.answer_author)["reputation"], 15)

        replacement = self.post(self.client_for(self.question_author), second_url, {})
        self.assertEqual(replacement.status_code, 200, replacement.content)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_accepted)
        self.assertTrue(second.is_accepted)
        self.assertEqual(Answer.objects.filter(question=question, is_accepted=True).count(), 1)
        self.assertEqual(get_reputation_summary(self.answer_author)["reputation"], 0)
        self.assertEqual(get_reputation_summary(self.other_user)["reputation"], 15)

        unaccepted = self.delete(self.client_for(self.question_author), second_url)
        self.assertEqual(unaccepted.status_code, 200)
        self.assertFalse(unaccepted.json()["is_accepted"])
        self.assertEqual(get_reputation_summary(self.other_user)["reputation"], 0)

    def test_accepting_answer_from_another_question_is_rejected(self):
        question = self.make_question()
        other_question = self.make_question()
        foreign_answer = self.make_answer(other_question)

        response = self.post(
            self.client_for(self.question_author),
            f"/api/v1/questions/{question.pk}/answers/{foreign_answer.pk}/accept/",
            {},
        )

        self.assertEqual(response.status_code, 400)
        foreign_answer.refresh_from_db()
        self.assertFalse(foreign_answer.is_accepted)

    def test_one_accepted_answer_per_question_database_constraint(self):
        question = self.make_question()
        first = self.make_answer(question, body="First.")
        second = self.make_answer(question, body="Second.")
        first.is_accepted = True
        first.save(update_fields=("is_accepted",))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                second.is_accepted = True
                second.save(update_fields=("is_accepted",))

    def test_reputation_event_idempotency_and_compensation_preserve_history(self):
        question = self.make_question()
        event = create_reputation_event(
            user=self.question_author,
            actor=self.voter,
            event_type=ReputationEvent.EventType.QUESTION_UPVOTE,
            delta=5,
            source_type=ReputationEvent.SourceType.VOTE,
            source_id=123,
            idempotency_key="test:question-upvote:123",
        )
        duplicate = create_reputation_event(
            user=self.question_author,
            actor=self.voter,
            event_type=ReputationEvent.EventType.QUESTION_UPVOTE,
            delta=5,
            source_type=ReputationEvent.SourceType.VOTE,
            source_id=123,
            idempotency_key="test:question-upvote:123",
        )
        reversal = reverse_reputation_event(event, actor=self.voter)
        repeated_reversal = reverse_reputation_event(event, actor=self.voter)

        self.assertEqual(event.pk, duplicate.pk)
        self.assertEqual(reversal.pk, repeated_reversal.pk)
        self.assertEqual(ReputationEvent.objects.filter(user=self.question_author).count(), 2)
        self.assertEqual(get_reputation_summary(self.question_author)["reputation"], 0)

    def test_vote_award_failure_rolls_back_vote_and_ledger(self):
        question = self.make_question()

        with patch("apps.questions.services.create_reputation_event", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                from .services import cast_vote

                cast_vote(voter=self.voter, question_id=question.pk, value=Vote.Value.UPVOTE)

        self.assertFalse(Vote.objects.filter(question=question, voter=self.voter).exists())
        self.assertEqual(get_reputation_summary(self.question_author)["reputation"], 0)

    def test_replacement_award_failure_rolls_back_previous_acceptance_reversal(self):
        question = self.make_question()
        first = self.make_answer(question, author=self.answer_author, body="First answer.")
        second = self.make_answer(question, author=self.other_user, body="Second answer.")
        set_accepted_answer(
            question_id=question.pk,
            answer_id=first.pk,
            actor=self.question_author,
            accepted=True,
        )

        from . import services

        original_create_event = services.create_reputation_event
        calls = 0

        def fail_on_new_award(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated ledger write failure")
            return original_create_event(**kwargs)

        with patch("apps.questions.services.create_reputation_event", side_effect=fail_on_new_award):
            with self.assertRaises(RuntimeError):
                set_accepted_answer(
                    question_id=question.pk,
                    answer_id=second.pk,
                    actor=self.question_author,
                    accepted=True,
                )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_accepted)
        self.assertFalse(second.is_accepted)
        self.assertEqual(get_reputation_summary(self.answer_author)["reputation"], 15)
        self.assertEqual(get_reputation_summary(self.other_user)["reputation"], 0)

    def test_reputation_summary_endpoint(self):
        question = self.make_question()
        self.post(
            self.client_for(self.voter),
            f"/api/v1/questions/{question.pk}/vote/",
            {"value": 1},
        )

        response = self.client_for(self.other_user).get(
            f"/api/v1/users/{self.question_author.pk}/reputation/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reputation"], 5)
        self.assertEqual(response.json()["event_count"], 1)
