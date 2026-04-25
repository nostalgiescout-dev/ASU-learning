from __future__ import annotations

from kechafa_app.repositories.base_repo import BaseRepository


class AIConversationRepository(BaseRepository):
    def list_for_user(self, user_id: int):
        return self.fetchall(
            """
            SELECT *
            FROM ai_conversations
            WHERE user_id=?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        )

    def latest_for_user(self, user_id: int):
        return self.fetchone(
            "SELECT * FROM ai_conversations WHERE user_id=? ORDER BY updated_at DESC, id DESC LIMIT 1",
            (user_id,),
        )

    def get_for_user(self, user_id: int, conversation_id: int):
        return self.fetchone(
            "SELECT * FROM ai_conversations WHERE id=? AND user_id=?",
            (conversation_id, user_id),
        )

    def create_conversation(self, user_id: int, title: str, history_json: str) -> int:
        return self.execute(
            """
            INSERT INTO ai_conversations (user_id, title, history_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (user_id, title, history_json),
        )

    def persist_history(self, conversation_id: int, history_json: str, title: str | None = None) -> None:
        if title is None:
            self.execute(
                "UPDATE ai_conversations SET history_json=?, updated_at=datetime('now') WHERE id=?",
                (history_json, conversation_id),
            )
            return
        self.execute(
            "UPDATE ai_conversations SET history_json=?, title=?, updated_at=datetime('now') WHERE id=?",
            (history_json, title, conversation_id),
        )

    def clear_history(self, conversation_id: int, title: str | None = None) -> None:
        if title is None:
            self.execute(
                "UPDATE ai_conversations SET history_json='[]', updated_at=datetime('now') WHERE id=?",
                (conversation_id,),
            )
            return
        self.execute(
            "UPDATE ai_conversations SET history_json='[]', title=?, updated_at=datetime('now') WHERE id=?",
            (title, conversation_id),
        )

    def rename_conversation(self, conversation_id: int, title: str) -> None:
        self.execute(
            "UPDATE ai_conversations SET title=?, updated_at=datetime('now') WHERE id=?",
            (title, conversation_id),
        )

    def delete_conversation(self, conversation_id: int) -> None:
        self.execute("DELETE FROM ai_conversations WHERE id=?", (conversation_id,))
