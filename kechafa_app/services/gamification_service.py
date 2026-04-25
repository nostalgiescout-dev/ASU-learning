from __future__ import annotations

import math

from kechafa_app.repositories.user_repository import UserRepository


class GamificationService:
    XP_REWARDS = {
        "registration": 100,
        "lesson_complete": 20,
        "course_complete": 150,
        "daily_login": 10,
        "message_sent": 5,
        "book_downloaded": 5,
    }

    def __init__(self):
        self.user_repo = UserRepository()

    def award_xp(self, user_id: int, action: str) -> dict:
        xp = self.XP_REWARDS.get(action, 0)
        if xp <= 0:
            return {"xp": 0, "level_up": False}

        user = self.user_repo.get_by_id(user_id)
        old_level = self._compute_level((user or {}).get("level_points", 0))
        self.user_repo.increment_xp(user_id, xp)
        refreshed = self.user_repo.get_by_id(user_id)
        new_level = self._compute_level((refreshed or {}).get("level_points", 0))
        return {"xp": xp, "level_up": new_level > old_level, "new_level": new_level}

    @staticmethod
    def _compute_level(xp: int) -> int:
        return int(math.sqrt(max(xp, 0) / 100)) + 1
