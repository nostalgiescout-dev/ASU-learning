# Academic Kechafa Upgrade Roadmap

This repository has been upgraded toward a cleaner architecture in progressive phases.

## Phase 1 completed in code

- Application package introduced under `kechafa_app/`
- Centralized config, extension registry, and error handling
- Blueprint registration isolated from the entrypoint
- Repository and service layers introduced
- Authentication route migrated to `AuthService`
- AI coach route migrated to `AIService`
- Messages route migrated to `MessageService`
- Gamification and notification services created
- Docker, CI, and pytest scaffolding added

## Phase 2 recommended next

- Migrate dashboard, library, and courses to services/repositories
- Replace raw SQL helpers with SQLAlchemy repositories
- Add Flask-Migrate and database models as the single source of truth
- Add Redis and Celery for caching and AI background work
- Integrate RAG indexing for books and lessons

## Phase 3 recommended next

- PostgreSQL production migration
- WebSocket notifications and live chat
- AI-generated quizzes and learning paths
- Role-based admin analytics dashboards
