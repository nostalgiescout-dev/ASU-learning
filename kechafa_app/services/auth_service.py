from __future__ import annotations

from dataclasses import dataclass, field

from werkzeug.security import check_password_hash, generate_password_hash

from kechafa_app.repositories.base_repo import BaseRepository
from kechafa_app.repositories.user_repository import UserRepository
from kechafa_app.services.gamification_service import GamificationService
from kechafa_app.services.notification_service import NotificationService
from kechafa_app.services.email_service import send_verification_email


@dataclass
class RegistrationResult:
    user_id: int | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and self.user_id is not None


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.base_repo = BaseRepository()
        self.notifications = NotificationService()
        self.gamification = GamificationService()

    def validate_registration(self, username: str, email: str, password: str) -> list[str]:
        errors: list[str] = []
        if len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if self.user_repo.get_by_username(username):
            errors.append("Username already taken.")
        if "@" not in email:
            errors.append("Valid email required.")
        if self.user_repo.get_by_email(email):
            errors.append("Email already registered.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        return errors

    def register_user(self, *, username: str, email: str, password: str, full_name: str, scout_unit: str, lang: str) -> RegistrationResult:
        errors = self.validate_registration(username, email, password)
        if errors:
            return RegistrationResult(errors=errors)

        user_id = self.user_repo.create(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            full_name=full_name,
            scout_unit=scout_unit,
            lang=lang,
        )

        badge = self.base_repo.fetchone("SELECT id FROM badges WHERE name='First Steps'")
        if badge:
            self.base_repo.execute(
                "INSERT OR IGNORE INTO user_badges (user_id,badge_id) VALUES (?,?)",
                (user_id, badge["id"]),
            )

        self.notifications.create(
            user_id,
            "welcome",
            "Welcome to Academic Kechafa!",
            "You earned your first XP and can now start learning.",
            "tada",
            target_url=f"/profile/{username}",
            entity_type="user",
            entity_id=user_id,
            actor_id=user_id,
        )
        self.gamification.award_xp(user_id, "registration")

        # Send verification email (non-blocking — failure doesn't block registration)
        send_verification_email(email, username)

        return RegistrationResult(user_id=user_id)

    def authenticate(self, identifier: str, password: str):
        user = self.user_repo.get_by_identifier(identifier)
        if not user or not user.get("is_active"):
            return None, "invalid"
        if not check_password_hash(user["password_hash"], password):
            return None, "invalid"
        if not user.get("is_verified", 1):
            return None, "unverified"
        self.user_repo.update_last_seen(user["id"])
        return user, None

    def set_language(self, user_id: int | None, lang: str) -> None:
        if user_id:
            self.user_repo.update_language(user_id, lang)
