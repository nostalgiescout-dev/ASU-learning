from __future__ import annotations

from kechafa_app.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository):
    def get_by_id(self, user_id: int):
        return self.fetchone("SELECT * FROM users WHERE id=?", (user_id,))

    def get_by_username(self, username: str):
        return self.fetchone("SELECT * FROM users WHERE username=?", (username,))

    def get_by_email(self, email: str):
        return self.fetchone("SELECT * FROM users WHERE email=?", (email,))

    def get_by_identifier(self, identifier: str):
        return self.get_by_email(identifier) or self.get_by_username(identifier)

    def update_last_seen(self, user_id: int) -> None:
        self.execute("UPDATE users SET last_seen=datetime('now') WHERE id=?", (user_id,))

    def update_language(self, user_id: int, lang: str) -> None:
        self.execute("UPDATE users SET preferred_lang=? WHERE id=?", (lang, user_id))

    def create(self, *, username: str, email: str, password_hash: str, full_name: str, scout_unit: str, lang: str):
        return self.execute(
            "INSERT INTO users (username,email,password_hash,full_name,scout_unit,preferred_lang,level_points,level_rank,is_verified) "
            "VALUES (?,?,?,?,?,?,100,1,0)",
            (username, email, password_hash, full_name, scout_unit, lang),
        )

    def verify_email(self, email: str) -> None:
        self.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))

    def increment_xp(self, user_id: int, xp: int) -> None:
        self.execute("UPDATE users SET level_points=level_points+? WHERE id=?", (xp, user_id))
        self.execute("UPDATE users SET level_rank=MAX(1, level_points / 1000) WHERE id=?", (user_id,))

    def create_google_user(self, *, email: str, full_name: str, avatar_url: str, lang: str) -> int:
        import re, secrets
        base = re.sub(r"[^a-z0-9]", "", full_name.lower().replace(" ", "_")) or "scout"
        username = base
        counter = 1
        while self.fetchone("SELECT id FROM users WHERE username=?", (username,)):
            username = f"{base}{counter}"
            counter += 1
        return self.execute(
            "INSERT INTO users (username,email,password_hash,full_name,avatar_url,preferred_lang,"
            "level_points,level_rank,is_verified) VALUES (?,?,?,?,?,?,100,1,1)",
            (username, email, secrets.token_hex(32), full_name, avatar_url, lang),
        )

    def update_avatar(self, user_id: int, avatar_url: str) -> None:
        self.execute("UPDATE users SET avatar_url=? WHERE id=?", (avatar_url, user_id))
