# Academic Kechafa

Academic Kechafa is a Flask-based e-learning and community platform built for scouting-oriented learning. The project combines courses, lesson tracking, a community feed, direct messaging, PDF library access, notifications, multilingual UI, and an optional AI coach.

## What the Project Includes

- Role-based access for `admin`, `instructor`, and `scout`
- Course catalog with categories, lessons, quizzes, and progress tracking
- Community feed with text, video, reel, course, and book announcement posts
- Direct messaging between users
- AI coach chat with conversation history and optional OpenRouter integration
- PDF library with category management and per-user access grants
- Notifications for access grants, course activity, feed activity, and messaging
- Multilingual support with `en`, `ar`, `fr`, and `es`
- Auto-seeded demo data for local development

## Stack

- Python
- Flask 3
- SQLite
- Raw SQL with a lightweight database helper layer
- Jinja templates
- Optional OpenRouter / OpenAI-compatible AI integration
- Docker and Docker Compose for containerized local runs

## Project Structure

```text
ELearning/
|- app.py                      # local entrypoint
|- database.py                 # SQLite schema, helpers, and seed data
|- i18n.py                     # translation helpers
|- requirements.txt
|- docker-compose.yml
|- Dockerfile
|- kechafa_app/
|  |- __init__.py              # app factory
|  |- config.py                # environment-based configuration
|  |- extensions.py
|  |- api/__init__.py          # blueprint registration
|  |- core/                    # auth decorators and error handlers
|  |- repositories/            # data access helpers
|  |- services/                # business logic layer
|- routes/
|  |- auth.py
|  |- dashboard.py
|  |- courses.py
|  |- library.py
|  |- messages.py
|  |- ai_coach.py
|  |- notifications.py
|  |- profile.py
|  |- admin.py
|  |- content/
|- templates/                  # Jinja templates grouped by feature
|- static/
|  |- uploads/                 # avatars, lesson videos, books, feed media
|- tests/                      # service-level tests
|- docs/                       # architecture and upgrade notes
```

## Local Setup

### 1. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
# Windows PowerShell
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and adjust the values you need.

Important notes:

- The app loads `.env` automatically from the project root.
- If no database exists yet, the app creates `kechafa.db` and seeds demo data on first run.
- AI chat works in a disabled/offline-safe mode unless live AI is explicitly enabled.

### 4. Run the app

```bash
python app.py
```

Default URL:

```text
http://localhost:5000
```

The app binds to `0.0.0.0` by default, so you can also open it from another device on the same local network by using your machine's local IP address.

### Optional: Run the app over HTTPS locally

For quick local HTTPS, use Flask's ad-hoc certificate support:

```bash
# Windows PowerShell
$env:FLASK_SSL_MODE="adhoc"
python app.py
```

Then open:

```text
https://localhost:5000
```

Your browser will usually show a warning because the certificate is self-signed.

If you already have certificate files, you can use them directly:

```bash
# Windows PowerShell
$env:SSL_CERT_FILE="C:\path\to\cert.pem"
$env:SSL_KEY_FILE="C:\path\to\key.pem"
python app.py
```

## Environment Variables

The main settings used by this project are:

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret | `kechafa-dev-secret-2024` |
| `FLASK_ENV` | App config name | `development` |
| `KECHAFA_DB` | SQLite file path | `kechafa.db` |
| `DEFAULT_LANGUAGE` | Default UI language | `en` |
| `ENABLE_REAL_AI` | Enables live AI responses | `false` |
| `OPENROUTER_API_KEY` | Primary OpenRouter API key | empty |
| `OPENROUTER_FALLBACK_API_KEY` | Backup OpenRouter API key | empty |
| `OPENROUTER_MODEL` | OpenRouter model name | `openrouter/free` |
| `OPENROUTER_MAX_TOKENS` | Response token cap | `512` |
| `OPENROUTER_APP_URL` | Referer header for OpenRouter | empty or local URL |
| `OPENROUTER_APP_TITLE` | App title sent to OpenRouter | `Academic Kechafa` |
| `MAX_CONTENT_LENGTH_MB` | Upload size limit in MB | `250` |
| `REDIS_URL` | Reserved for future use | `redis://localhost:6379/0` |
| `FLASK_SSL_MODE` | Local HTTPS mode, supports `adhoc` | empty |
| `SSL_CERT_FILE` | Path to TLS certificate for local run | empty |
| `SSL_KEY_FILE` | Path to TLS private key for local run | empty |
| `FORCE_HTTPS` | Redirect HTTP requests to HTTPS | `false` |
| `TRUST_PROXY_HEADERS` | Trust `X-Forwarded-*` headers from a reverse proxy | `false` |
| `PREFERRED_URL_SCHEME` | Default URL scheme used by Flask | `http` or `https` in production |

## Demo Accounts

On a fresh local database, these accounts are created automatically:

| Role | Username | Password |
|---|---|---|
| Scout | `scout_sara` | `Scout@1234` |
| Instructor | `lead_instructor` | `Instructor@1234` |
| Admin | `kechafa_admin` | `Admin@1234` |

If `kechafa.db` already exists, the app will keep the existing data instead of reseeding users.

## Core Feature Areas

### Authentication and Roles

- Registration and login
- Session-based auth
- Role-aware access control decorators in `kechafa_app/core/security.py`

### Courses

- Course categories and difficulty levels
- Instructor/admin course creation and editing
- Lesson management with URL-based or uploaded videos
- Lesson completion tracking
- Quiz support on lessons
- Course access requests for scouts

### Community Feed

- Text posts
- Video and reel posts
- Post comments, likes, and shares
- Course and book announcement posts
- Friend suggestions and request actions

### Messaging and AI

- Direct messaging threads between users
- AI coach conversations stored per user
- Rename, clear, delete, and edit AI conversations
- Live AI replies through OpenRouter when enabled

### Library

- PDF upload and organization by category
- Admin-controlled access grants
- View and download flows with permission checks

### Notifications

- Feed interaction notifications
- Course access and lesson notifications
- Book access notifications
- Basic unread tracking and "mark as read" flows

## Main Routes

| Area | Route |
|---|---|
| Public landing | `/` |
| Login | `/login` |
| Register | `/register` |
| Feed | `/feed` |
| Profile | `/profile/<username>` |
| Courses | `/courses` |
| Messages | `/messages` |
| AI coach | `/ai-coach` |
| Library | `/library` |
| Notifications | `/notifications` |
| Admin | `/admin` |
| Content pages | `/content/...` |

## Running Tests

```bash
pytest -q
```

Current tests focus on the service layer, including authentication, friendships, gamification, and messaging.

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

The provided Compose file exposes the app on port `5000` and mounts the project directory into the container for local development.

## HTTPS In Production

For production, the recommended setup is to put the Flask app behind a reverse proxy such as Nginx or Caddy, terminate TLS there, and forward traffic to this app over HTTP.

Recommended environment variables for that setup:

```bash
FORCE_HTTPS=true
TRUST_PROXY_HEADERS=true
PREFERRED_URL_SCHEME=https
FLASK_ENV=production
```

Notes:

- `TRUST_PROXY_HEADERS=true` lets Flask respect `X-Forwarded-Proto` from the proxy.
- `FORCE_HTTPS=true` redirects plain HTTP traffic to HTTPS.
- `SESSION_COOKIE_SECURE` is already enabled in production.

## Data and Upload Notes

- SQLite data is stored in `kechafa.db` by default.
- Uploaded files are stored under `static/uploads/`.
- Lesson video uploads are saved under `static/uploads/content/lesson/`.
- Feed media uploads are saved under `static/uploads/content/feed/`.
- Library PDFs are saved under `static/uploads/books/`.

## AI Integration Notes

To enable live AI replies:

1. Set `ENABLE_REAL_AI=true`
2. Provide `OPENROUTER_API_KEY`
3. Optionally set `OPENROUTER_MODEL`

If live AI is not enabled, the AI coach UI still loads, but message sends will return a disabled/unavailable response instead of calling the network.

## Useful Files

- `app.py` - local run entrypoint
- `kechafa_app/__init__.py` - app factory and request lifecycle setup
- `database.py` - schema creation and demo seeding
- `docs/platform_architecture.md` - architecture notes
- `docs/upgrade_roadmap.md` - planned improvement notes
