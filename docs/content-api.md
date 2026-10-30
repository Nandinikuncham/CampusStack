# Questions, tags, answers, and comments API

All content endpoints require an authenticated CampusStack session, matching the existing DRF default permission. Unsafe requests must include the session CSRF cookie and its matching `X-CSRFToken` header; use `GET /api/v1/auth/csrf/` to obtain a token. Question and tag reads are therefore limited to authenticated users in this phase.

## Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET, POST | `/api/v1/questions/` | Paginated question list and creation |
| GET, PATCH, DELETE | `/api/v1/questions/{id}/` | Retrieve or modify a question |
| GET, POST | `/api/v1/questions/{id}/answers/` | List or add answers to an open question |
| GET, PATCH, DELETE | `/api/v1/answers/{id}/` | Retrieve or modify an answer |
| GET, POST | `/api/v1/questions/{id}/comments/` | List or add question comments |
| GET, POST | `/api/v1/answers/{id}/comments/` | List or add answer comments |
| GET, POST | `/api/v1/comments/` | List comments or create one with exactly one target |
| GET, PATCH, DELETE | `/api/v1/comments/{id}/` | Retrieve or modify a comment |
| GET, POST | `/api/v1/tags/` | List tags; create tags as an administrator |
| GET, PATCH, DELETE | `/api/v1/tags/{id}/` | Retrieve or manage tags as an administrator |

Question lists support `?tag={slug}`, `?search={text}`, `?ordering=created_at` (or `-created_at`, `updated_at`, `title`), and pagination with `?page=` / `?page_size=`. The default page size is 20 and the maximum is 100.

Question create body fields: `title`, `description`, optional `department`, optional `status`, and optional `tags` as existing tag slugs. The author is always the authenticated user. Answers accept only a non-empty `body`; the question and author come from the nested URL and session. Comments accept non-empty `content`; generic comment creation requires exactly one existing `question` or `answer` ID. Nested comment routes bind the target from the URL and reject conflicting supplied targets.

Successful creation returns `201`; reads/updates return `200`; deletes return `204`. Invalid input returns `400`, unauthenticated/unauthorized writes return `403`, and missing resource IDs return `404`.

Only question/answer/comment authors or administrators may edit/delete content. Any authenticated user may answer an open question. Answer creation on closed questions is rejected. Tag creation, editing and deletion require an administrator; names are lowercased and whitespace-normalized, slugs are normalized, and the database enforces unique names/slugs.

**Multiple answers per question are allowed.** This permits a user to add distinct valid approaches; each answer is independently authored and editable by its author or an administrator.

Comments have a database XOR constraint so each row belongs to a question or an answer, never both or neither. No voting, accepted-answer, reputation, badge, notification, or AI behavior is included.
