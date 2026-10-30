# Following and mentorship

All routes are under `/api/v1/`. State-changing requests use the existing session authentication and CSRF protections.

## Following

- `POST` / `DELETE` `/users/{user_id}/follow/` follows or unfollows a user. Self-follow is rejected; duplicate follows are idempotent at the API and prevented by a unique database constraint.
- `GET` `/users/{user_id}/followers/` and `/users/{user_id}/following/` return paginated lists with only public user fields.
- `POST` / `DELETE` `/tags/{tag_id}/follow/` follows or unfollows an existing tag.
- `GET` `/tags/followed/` returns the authenticated user's followed tags. Tag responses expose follower counts.
- Public profiles expose follower and following counts.

## Mentorship eligibility

Only active STUDENT accounts with a current JUNIOR or SENIOR academic status may request mentorship. SENIOR students are permitted to seek peer mentoring. Eligible mentors are active SENIOR or ALUMNI students, and active FACULTY accounts whose faculty profile is APPROVED. Academic status is calculated by the existing academic progression service; the client cannot supply it. FACULTY, ADMIN, ALUMNI, and junior students cannot request student mentorship.

## Request state transitions

Permitted request transitions are:

```text
PENDING -> APPROVED -> COMPLETED
PENDING -> REJECTED
PENDING -> CANCELLED
```

Only the intended mentor can approve or reject a pending request. Approval atomically creates one ACTIVE `Mentorship` record. The student can cancel only their own pending request. Either participant can complete an active mentorship; completion marks both the relationship and request completed. Other transitions are rejected. Database constraints prevent self-relationships, duplicate pending requests, and duplicate active student/mentor pairs.

Requests are private: sent and received lists are scoped to the authenticated student or mentor, and transition routes hide records from unrelated users. No administrator moderation bypass is provided. Important creation and state transitions are recorded in `AuditEvent`; audit metadata contains identifiers and statuses, never the request message.

## Mentorship endpoints

- `POST` `/mentorship/requests/` with `mentor_id` and a short `message`.
- `GET` `/mentorship/requests/sent/` and `/mentorship/requests/received/` for the caller's requests.
- `POST` `/mentorship/requests/{request_id}/approve/`, `/reject/`, or `/cancel/` subject to the transition rules above.
- `GET` `/mentorship/relationships/` lists the caller's active relationships.
- `POST` `/mentorship/relationships/{mentorship_id}/complete/` completes an active relationship for either participant.
