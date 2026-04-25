from __future__ import annotations

from kechafa_app.repositories.base_repo import BaseRepository


class FriendRepository(BaseRepository):
    def get_user_summary(self, user_id: int):
        return self.fetchone(
            """
            SELECT id, username, full_name, avatar_url, role, scout_unit, is_active
            FROM users
            WHERE id=?
            """,
            (user_id,),
        )

    def get_latest_friendship(self, user_id: int, other_user_id: int):
        return self.fetchone(
            """
            SELECT *
            FROM friend_requests
            WHERE (sender_id=? AND receiver_id=?)
               OR (sender_id=? AND receiver_id=?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, other_user_id, other_user_id, user_id),
        )

    def accept_request(self, request_id: int) -> None:
        self.execute(
            "UPDATE friend_requests SET status='accepted', responded_at=datetime('now') WHERE id=?",
            (request_id,),
        )

    def create_request(self, sender_id: int, receiver_id: int) -> int:
        return self.execute(
            "INSERT INTO friend_requests (sender_id, receiver_id, status) VALUES (?, ?, 'pending')",
            (sender_id, receiver_id),
        )

    def list_friends_for_user(self, user_id: int):
        return self.fetchall(
            """
            SELECT
                u.id,
                u.username,
                u.full_name,
                u.avatar_url,
                u.role,
                u.scout_unit,
                fr.responded_at,
                (
                    SELECT t.id
                    FROM threads t
                    WHERE (t.participant_a=? AND t.participant_b=u.id)
                       OR (t.participant_a=u.id AND t.participant_b=?)
                    ORDER BY t.updated_at DESC, t.id DESC
                    LIMIT 1
                ) AS thread_id
            FROM friend_requests fr
            JOIN users u
              ON u.id = CASE
                    WHEN fr.sender_id=? THEN fr.receiver_id
                    ELSE fr.sender_id
                END
            WHERE fr.status='accepted'
              AND (fr.sender_id=? OR fr.receiver_id=?)
            ORDER BY COALESCE(fr.responded_at, fr.created_at) DESC, u.full_name, u.username
            """,
            (user_id, user_id, user_id, user_id, user_id),
        )

    def list_friend_suggestions(self, user_id: int, limit: int = 8):
        return self.fetchall(
            """
            SELECT
                u.id,
                u.username,
                u.full_name,
                u.avatar_url,
                u.role,
                u.scout_unit,
                COALESCE((
                    SELECT fr.status
                    FROM friend_requests fr
                    WHERE (
                        (fr.sender_id = ? AND fr.receiver_id = u.id)
                        OR (fr.sender_id = u.id AND fr.receiver_id = ?)
                    )
                    ORDER BY fr.id DESC
                    LIMIT 1
                ), 'none') AS friend_status,
                EXISTS(
                    SELECT 1
                    FROM friend_requests fr
                    WHERE fr.sender_id = u.id
                      AND fr.receiver_id = ?
                      AND fr.status = 'pending'
                ) AS incoming_request
            FROM users u
            WHERE u.id != ?
              AND u.is_active=1
            ORDER BY u.last_seen DESC, u.created_at DESC
            LIMIT ?
            """,
            (user_id, user_id, user_id, user_id, limit),
        )
