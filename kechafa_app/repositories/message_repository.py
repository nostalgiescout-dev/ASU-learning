from __future__ import annotations

from kechafa_app.repositories.base_repo import BaseRepository


class MessageRepository(BaseRepository):
    def list_threads_for_user(self, user_id: int):
        return self.fetchall(
            """
            SELECT
                t.*,
                CASE WHEN t.participant_a=? THEN t.participant_b ELSE t.participant_a END AS other_id,
                (
                    SELECT body
                    FROM messages
                    WHERE thread_id=t.id
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                ) AS last_body,
                (
                    SELECT created_at
                    FROM messages
                    WHERE thread_id=t.id
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                ) AS last_time,
                (
                    SELECT COUNT(*)
                    FROM messages
                    WHERE thread_id=t.id AND receiver_id=? AND is_read=0
                ) AS unread_count
            FROM threads t
            WHERE t.participant_a=? OR t.participant_b=?
            ORDER BY t.updated_at DESC, t.id DESC
            """,
            (user_id, user_id, user_id, user_id),
        )

    def get_thread_for_user(self, user_id: int, thread_id: int):
        return self.fetchone(
            """
            SELECT *
            FROM threads
            WHERE id=? AND (participant_a=? OR participant_b=?)
            """,
            (thread_id, user_id, user_id),
        )

    def find_direct_thread(self, user_a: int, user_b: int):
        return self.fetchone(
            """
            SELECT *
            FROM threads
            WHERE (participant_a=? AND participant_b=?)
               OR (participant_a=? AND participant_b=?)
            LIMIT 1
            """,
            (user_a, user_b, user_b, user_a),
        )

    def create_thread(self, participant_a: int, participant_b: int) -> int:
        return self.execute(
            """
            INSERT INTO threads (participant_a, participant_b, updated_at)
            VALUES (?, ?, datetime('now'))
            """,
            (participant_a, participant_b),
        )

    def create_message(self, body: str, sender_id: int, receiver_id: int, thread_id: int) -> int:
        return self.execute(
            """
            INSERT INTO messages (body, sender_id, receiver_id, thread_id)
            VALUES (?, ?, ?, ?)
            """,
            (body, sender_id, receiver_id, thread_id),
        )

    def touch_thread(self, thread_id: int) -> None:
        self.execute("UPDATE threads SET updated_at=datetime('now') WHERE id=?", (thread_id,))

    def list_thread_messages(self, thread_id: int):
        return self.fetchall(
            """
            SELECT
                m.*,
                u.username,
                u.full_name,
                u.avatar_url AS uavatar,
                u.role AS user_role
            FROM messages m
            JOIN users u ON m.sender_id=u.id
            WHERE m.thread_id=?
            ORDER BY m.created_at ASC, m.id ASC
            """,
            (thread_id,),
        )

    def mark_thread_as_read(self, thread_id: int, user_id: int) -> None:
        self.execute(
            """
            UPDATE messages
            SET is_read=1
            WHERE thread_id=? AND receiver_id=? AND is_read=0
            """,
            (thread_id, user_id),
        )

    def list_instructors(self):
        return self.fetchall(
            """
            SELECT id, username, full_name, avatar_url, role
            FROM users
            WHERE role='instructor' AND is_active=1
            ORDER BY COALESCE(full_name, username), id
            """
        )

    def get_user_summary(self, user_id: int):
        return self.fetchone(
            """
            SELECT id, username, full_name, avatar_url, role, is_active
            FROM users
            WHERE id=?
            """,
            (user_id,),
        )
