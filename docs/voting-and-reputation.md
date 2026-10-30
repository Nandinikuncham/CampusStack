# Voting and reputation

## Scoring rules

Reputation is awarded to the author of the content being rated:

| Action | Points |
| --- | ---: |
| Question upvote | +5 |
| Question downvote | -2 |
| Answer upvote | +10 |
| Answer downvote | -2 |
| Accepted answer | +15 |

The defaults are defined by `REPUTATION_POINTS` in Django settings and can be overridden through environment-specific settings without changing application code.

## Ledger behavior

`ReputationEvent` is append-only application history. An award has a deterministic idempotency key. When a vote changes or is removed, or an accepted answer is unaccepted or replaced, the service appends a compensating event with the opposite delta; it does not delete the original event. Vote and acceptance changes plus their ledger events run in database transactions. Current reputation is the sum of a user's ledger deltas, exposed at `GET /api/v1/users/{user_id}/reputation/`.

Question and answer vote actions use `POST` with `{"value": 1}` for upvote or `{"value": -1}` for downvote, and `DELETE` to remove the caller's vote. Acceptance uses `POST` or `DELETE` at `/api/v1/questions/{question_id}/answers/{answer_id}/accept/`.

Scores in question and answer responses are derived from active stored votes: `upvote_count`, `downvote_count`, and `score` (upvotes minus downvotes). Clients cannot submit score values. Database uniqueness constraints prevent more than one vote per voter and content item, and a target constraint requires each vote to target exactly one question or answer.
