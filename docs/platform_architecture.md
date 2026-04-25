# AI Learning Platform Architecture

This document defines a scalable Flask + SQLite architecture for a final-year project (PFE) focused on AI-powered learning and content sharing.

## 1. Project Structure

```text
anwar/
├── app.py
├── config.py
├── database.py
├── schema_v2.sql
├── requirements.txt
├── docs/
│   └── platform_architecture.md
├── routes/
│   ├── auth.py
│   ├── admin.py
│   ├── users.py
│   ├── courses.py
│   ├── videos.py
│   ├── comments.py
│   ├── likes.py
│   ├── messages.py
│   ├── analytics.py
│   └── oauth.py
├── services/
│   ├── auth_service.py
│   ├── course_service.py
│   ├── analytics_service.py
│   ├── message_service.py
│   └── video_service.py
├── utils/
│   ├── decorators.py
│   ├── validators.py
│   └── security.py
├── templates/
│   ├── base.html
│   ├── partials/
│   │   ├── navbar.html
│   │   ├── sidebar.html
│   │   └── flash.html
│   ├── auth/
│   ├── admin/
│   ├── courses/
│   ├── videos/
│   ├── messages/
│   └── users/
└── static/
    ├── css/
    ├── js/
    └── uploads/
```

## 2. Architecture Principles

- Raw SQL only, with a small database helper layer.
- Blueprints per domain, not per page.
- Business logic in `services/`, not embedded deeply in routes.
- Decorators for access control.
- Templates grouped by feature.
- Separate analytics queries from CRUD routes.
- OAuth isolated in its own module.

## 3. Normalized Database Design

Core tables:

- `users`
- `courses`
- `videos`
- `enrollments`
- `video_views`
- `likes`
- `comments`
- `conversations`
- `conversation_participants`
- `messages`
- `oauth_accounts`

Why this design:

- `videos.course_id IS NULL` means public reel.
- `likes` has one row per `(user_id, video_id)`.
- `video_views` tracks who watched what and when for analytics.
- messaging is normalized around conversations instead of duplicated inbox rows.
- Google auth stays flexible via `oauth_accounts`.

## 4. Route Organization

### `routes/auth.py`

- `GET/POST /login`
- `GET/POST /register`
- `POST /logout`

### `routes/oauth.py`

- `GET /auth/google`
- `GET /auth/google/callback`

### `routes/users.py`

- `GET /users`
- `GET /users/<int:user_id>`

Admin only:

- `GET/POST /admin/users/create`
- `POST /admin/users/<int:user_id>/delete`

### `routes/courses.py`

- `GET /courses`
- `GET /courses/<int:course_id>`
- `POST /courses/<int:course_id>/enroll`

Admin only:

- `GET/POST /admin/courses/create`
- `GET/POST /admin/courses/<int:course_id>/edit`
- `POST /admin/courses/<int:course_id>/delete`
- `POST /admin/courses/<int:course_id>/assign-user`
- `GET /admin/courses/<int:course_id>/students`

### `routes/videos.py`

- `GET /videos/<int:video_id>`
- `GET /reels`

Admin only:

- `GET/POST /admin/videos/create`
- `GET/POST /admin/videos/<int:video_id>/edit`
- `POST /admin/videos/<int:video_id>/delete`

### `routes/likes.py`

- `POST /videos/<int:video_id>/like`

### `routes/comments.py`

- `POST /videos/<int:video_id>/comments`
- `GET /videos/<int:video_id>/comments`

Admin only:

- `GET /admin/comments`

### `routes/messages.py`

- `GET /messages`
- `GET /messages/<int:conversation_id>`
- `POST /messages/start`
- `POST /messages/<int:conversation_id>/send`

### `routes/analytics.py`

Admin only:

- `GET /admin/dashboard`
- `GET /admin/courses/<int:course_id>/analytics`

## 5. Service Layer Responsibilities

### `auth_service.py`

- register local user
- verify password
- create session payload
- resolve Google user account

### `course_service.py`

- create/update/delete courses
- enroll user
- assign user to course by admin
- fetch course details and enrolled users

### `video_service.py`

- create/edit/delete videos
- fetch reels vs course videos
- register video views

### `analytics_service.py`

- course enrollment counts
- viewers per course
- likes per course
- comments per course

### `message_service.py`

- create conversation
- list inbox conversations
- send and read messages

## 6. Access Control

Recommended decorators:

- `login_required`
- `admin_required`
- `owner_or_admin_required` when needed later

Rules:

- Admin manages users, courses, analytics, comments moderation.
- Users can browse, enroll, watch, like, comment, and message.

## 7. Google Authentication Design

Recommended flow:

1. user clicks "Login with Google"
2. redirect to Google consent screen
3. Google returns email, provider id, full name
4. if email exists, link account if needed
5. if not exists, create user automatically
6. store provider mapping in `oauth_accounts`
7. create session and redirect to dashboard

Store:

- provider name
- provider user id
- user id
- email used at signup

## 8. UI Pages

### User Pages

- login/register
- course catalog
- course detail
- video detail with likes/comments
- reels feed
- inbox
- conversation thread
- profile

### Admin Pages

- admin dashboard
- users management
- courses management
- course analytics page
- video management
- comments moderation

## 9. Error Handling

- return `404` for missing records
- return `403` for forbidden admin actions
- validate all form inputs before SQL execution
- use transactions for multi-step writes
- protect against duplicate likes and duplicate enrollments with DB constraints

## 10. Scalability Notes

SQLite is suitable for a PFE/MVP. To stay migration-friendly:

- keep SQL centralized
- avoid SQLite-specific logic in routes
- use integer primary keys everywhere
- use normalized join tables
- later swap SQLite with PostgreSQL with minimal service-layer changes

## 11. Recommended Next Implementation Steps

1. Replace the current mixed schema with `schema_v2.sql`.
2. Add `video_views` and `oauth_accounts`.
3. Split admin CRUD from public routes.
4. Move analytics SQL into `services/analytics_service.py`.
5. Add Google OAuth in `routes/oauth.py`.
6. Add basic integration tests for auth, enrollments, likes, comments, and messaging.

