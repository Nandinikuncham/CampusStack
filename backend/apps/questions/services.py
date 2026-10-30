from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.accounts.models import User

from .models import Answer, Question, ReputationEvent, Vote


DEFAULT_REPUTATION_POINTS = {
    "question_upvote": 5,
    "question_downvote": -2,
    "answer_upvote": 10,
    "answer_downvote": -2,
    "answer_accepted": 15,
}


def reputation_points(rule):
    points = getattr(settings, "REPUTATION_POINTS", DEFAULT_REPUTATION_POINTS).get(rule)
    if type(points) is not int or points == 0:
        raise ImproperlyConfigured(f"REPUTATION_POINTS[{rule!r}] must be a non-zero integer.")
    return points


def _event_matches(event, *, user, actor, event_type, delta, source_type, source_id, reverses):
    return (
        event.user_id == user.pk
        and event.actor_id == getattr(actor, "pk", None)
        and event.event_type == event_type
        and event.delta == delta
        and event.source_type == source_type
        and event.source_id == source_id
        and event.reverses_id == getattr(reverses, "pk", None)
    )


def create_reputation_event(
    *,
    user,
    actor,
    event_type,
    delta,
    source_type,
    source_id,
    idempotency_key,
    reverses=None,
):
    """Create one ledger event per stable key; a key cannot silently change meaning."""
    existing = ReputationEvent.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if not _event_matches(
            existing,
            user=user,
            actor=actor,
            event_type=event_type,
            delta=delta,
            source_type=source_type,
            source_id=source_id,
            reverses=reverses,
        ):
            raise ValidationError("Reputation idempotency key conflicts with an existing event.")
        return existing

    event = ReputationEvent(
        user=user,
        actor=actor,
        event_type=event_type,
        delta=delta,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        reverses=reverses,
    )
    event.full_clean()
    event.save(force_insert=True)
    return event


def reverse_reputation_event(event, *, actor):
    """Append the unique compensating entry without altering ledger history."""
    if event is None:
        return None
    if event.event_type == ReputationEvent.EventType.REVERSAL:
        raise ValidationError("A reversal event cannot itself be reversed.")
    existing = ReputationEvent.objects.filter(reverses=event).first()
    if existing:
        return existing
    return create_reputation_event(
        user=event.user,
        actor=actor,
        event_type=ReputationEvent.EventType.REVERSAL,
        delta=-event.delta,
        source_type=event.source_type,
        source_id=event.source_id,
        idempotency_key=f"reversal:{event.pk}",
        reverses=event,
    )


def _vote_award(vote, target, actor):
    if vote.question_id:
        if vote.value == Vote.Value.UPVOTE:
            event_type = ReputationEvent.EventType.QUESTION_UPVOTE
            rule = "question_upvote"
        else:
            event_type = ReputationEvent.EventType.QUESTION_DOWNVOTE
            rule = "question_downvote"
    else:
        if vote.value == Vote.Value.UPVOTE:
            event_type = ReputationEvent.EventType.ANSWER_UPVOTE
            rule = "answer_upvote"
        else:
            event_type = ReputationEvent.EventType.ANSWER_DOWNVOTE
            rule = "answer_downvote"
    event = create_reputation_event(
        user=target.author,
        actor=actor,
        event_type=event_type,
        delta=reputation_points(rule),
        source_type=ReputationEvent.SourceType.VOTE,
        source_id=vote.pk,
        idempotency_key=f"vote:{vote.pk}:revision:{vote.revision}:award",
    )
    vote.reputation_event = event
    vote.save(update_fields=("reputation_event", "updated_at"))


@transaction.atomic
def cast_vote(*, voter, value, question_id=None, answer_id=None):
    """Create, change, or remove one user's vote with a matching ledger entry."""
    if bool(question_id) == bool(answer_id):
        raise ValidationError("A vote must target exactly one question or answer.")
    if value is not None and value not in Vote.Value.values:
        raise ValidationError({"value": "Vote must be 1 (upvote) or -1 (downvote)."})

    if question_id:
        target = Question.objects.select_for_update().get(pk=question_id)
        question, answer = target, None
        target_author = target.author
    else:
        target = Answer.objects.select_for_update().select_related("author").get(pk=answer_id)
        question, answer = None, target
        target_author = target.author

    if target_author.pk == voter.pk:
        raise PermissionDenied("Users cannot vote on their own content.")

    vote_query = Vote.objects.select_for_update().filter(voter=voter)
    if question is not None:
        vote_query = vote_query.filter(question=question)
    else:
        vote_query = vote_query.filter(answer=answer)
    vote = vote_query.first()

    if vote is None and value is None:
        return None
    if vote is not None and vote.is_active and vote.value == value:
        return vote

    if vote is not None and vote.is_active:
        reverse_reputation_event(vote.reputation_event, actor=voter)
        vote.is_active = False
        vote.reputation_event = None
        vote.revision += 1
        vote.save(update_fields=("is_active", "reputation_event", "revision", "updated_at"))
        if value is None:
            return vote

    if value is None:
        return vote

    if vote is None:
        vote = Vote.objects.create(
            voter=voter,
            question=question,
            answer=answer,
            value=value,
            is_active=True,
            revision=1,
        )
    else:
        vote.value = value
        vote.is_active = True
        vote.revision += 1
        vote.save(update_fields=("value", "is_active", "revision", "updated_at"))

    _vote_award(vote, target, voter)
    return vote


def _unaccept_answer(answer, *, actor):
    reverse_reputation_event(answer.acceptance_event, actor=actor)
    answer.is_accepted = False
    answer.acceptance_event = None
    answer.save(update_fields=("is_accepted", "acceptance_event", "updated_at"))


@transaction.atomic
def set_accepted_answer(*, question_id, answer_id, actor, accepted):
    """Accept/unaccept one answer, atomically replacing any prior accepted answer."""
    question = Question.objects.select_for_update().get(pk=question_id)
    if question.author_id != actor.pk:
        raise PermissionDenied("Only the question author may accept or unaccept an answer.")

    answer = Answer.objects.select_for_update().select_related("author").get(pk=answer_id)
    if answer.question_id != question.pk:
        raise ValidationError({"answer": "This answer does not belong to the specified question."})

    if accepted:
        if answer.is_accepted:
            return answer

        previous = (
            Answer.objects.select_for_update()
            .filter(question=question, is_accepted=True)
            .exclude(pk=answer.pk)
            .first()
        )
        if previous:
            _unaccept_answer(previous, actor=actor)

        answer.is_accepted = True
        answer.acceptance_revision += 1
        answer.save(update_fields=("is_accepted", "acceptance_revision", "updated_at"))
        answer.acceptance_event = create_reputation_event(
            user=answer.author,
            actor=actor,
            event_type=ReputationEvent.EventType.ANSWER_ACCEPTED,
            delta=reputation_points("answer_accepted"),
            source_type=ReputationEvent.SourceType.ANSWER_ACCEPTANCE,
            source_id=answer.pk,
            idempotency_key=(
                f"accepted-answer:{answer.pk}:revision:{answer.acceptance_revision}:award"
            ),
        )
        answer.save(update_fields=("acceptance_event", "updated_at"))
        return answer

    if answer.is_accepted:
        _unaccept_answer(answer, actor=actor)
    return answer


def annotate_vote_scores(queryset):
    active_votes = Q(votes__is_active=True)
    return queryset.annotate(
        upvote_count=Count("votes", filter=active_votes & Q(votes__value=Vote.Value.UPVOTE)),
        downvote_count=Count("votes", filter=active_votes & Q(votes__value=Vote.Value.DOWNVOTE)),
        score=Coalesce(
            Sum("votes__value", filter=active_votes),
            Value(0),
            output_field=IntegerField(),
        ),
    )


def get_vote_summary(target):
    summary = target.votes.filter(is_active=True).aggregate(
        upvote_count=Count("pk", filter=Q(value=Vote.Value.UPVOTE)),
        downvote_count=Count("pk", filter=Q(value=Vote.Value.DOWNVOTE)),
        score=Coalesce(
            Sum("value"),
            Value(0),
            output_field=IntegerField(),
        ),
    )
    return summary


def get_reputation_summary(user):
    return ReputationEvent.objects.filter(user=user).aggregate(
        reputation=Coalesce(Sum("delta"), Value(0), output_field=IntegerField()),
        event_count=Count("pk"),
    )
