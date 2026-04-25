from __future__ import annotations

from flask import url_for

from kechafa_app.repositories.base_repo import BaseRepository


class NotificationService(BaseRepository):
    def create(
        self,
        user_id: int,
        kind: str,
        title: str,
        body: str = "",
        icon: str = "bell",
        *,
        target_url: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        actor_id: int | None = None,
    ) -> int:
        return self.execute(
            """
            INSERT INTO notifications (
                user_id, kind, title, body, icon, target_url, entity_type, entity_id, actor_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, kind, title, body, icon, target_url, entity_type, entity_id, actor_id),
        )

    def list_for_user(self, user_id: int, *, unread_only: bool = False, limit: int | None = None) -> list[dict]:
        sql = """
            SELECT
                n.*,
                actor.username AS actor_username,
                actor.full_name AS actor_full_name,
                actor.avatar_url AS actor_avatar_url
            FROM notifications n
            LEFT JOIN users actor ON actor.id = n.actor_id
            WHERE n.user_id=?
        """
        params: list = [user_id]
        if unread_only:
            sql += " AND n.is_read=0"
        sql += " ORDER BY n.created_at DESC, n.id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        items = self.fetchall(sql, tuple(params))
        for item in items:
            item["open_url"] = url_for("notifications.open_notification", notification_id=item["id"])
            item["target_url"] = item.get("target_url") or url_for("notifications.index")
            item["created_label"] = self._format_timestamp(item.get("created_at"))
            item["actor_name"] = item.get("actor_full_name") or item.get("actor_username")
        return items

    def get_for_user(self, user_id: int, notification_id: int) -> dict | None:
        item = self.fetchone(
            """
            SELECT *
            FROM notifications
            WHERE id=? AND user_id=?
            """,
            (notification_id, user_id),
        )
        if not item:
            return None
        item["target_url"] = item.get("target_url") or url_for("notifications.index")
        return item

    def unread_count(self, user_id: int) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id=? AND is_read=0",
            (user_id,),
        )
        return int((row or {}).get("c") or 0)

    def mark_read(self, user_id: int, notification_id: int) -> None:
        self.execute(
            "UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",
            (notification_id, user_id),
        )

    def mark_all_read(self, user_id: int) -> None:
        self.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (user_id,))

    def mark_related_as_read(
        self,
        user_id: int,
        *,
        kind: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> None:
        clauses = ["user_id=?", "is_read=0"]
        params: list = [user_id]
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        if entity_type:
            clauses.append("entity_type=?")
            params.append(entity_type)
        if entity_id is not None:
            clauses.append("entity_id=?")
            params.append(entity_id)

        self.execute(
            f"UPDATE notifications SET is_read=1 WHERE {' AND '.join(clauses)}",
            tuple(params),
        )

    def notify_message_received(self, *, recipient_id: int, sender: dict, thread_id: int, message_preview: str) -> None:
        sender_name = self._actor_name(sender)
        self.create(
            recipient_id,
            "message_received",
            f"New message from {sender_name}",
            self._truncate(message_preview, 100),
            "chat",
            target_url=url_for("messages.inbox", thread=thread_id),
            entity_type="thread",
            entity_id=thread_id,
            actor_id=sender.get("id"),
        )

    def notify_post_published(self, *, user_id: int, post_id: int, title: str, post_type: str) -> None:
        label = {"text": "Text post", "video": "Video post", "reel": "Reel post"}.get(post_type, "Post")
        self.create(
            user_id,
            "post_published",
            f"{label} published",
            title,
            "document",
            target_url=f"{url_for('dashboard.feed')}#post-{post_id}",
            entity_type="feed_post",
            entity_id=post_id,
            actor_id=user_id,
        )

    def notify_post_liked(self, *, recipient_id: int, actor: dict, post_id: int, post_title: str) -> None:
        if recipient_id == actor.get("id"):
            return
        actor_name = self._actor_name(actor)
        self.create(
            recipient_id,
            "post_like",
            f"{actor_name} liked your post",
            self._truncate(post_title, 100),
            "heart",
            target_url=f"{url_for('dashboard.feed')}#post-{post_id}",
            entity_type="feed_post",
            entity_id=post_id,
            actor_id=actor.get("id"),
        )

    def notify_post_commented(self, *, recipient_id: int, actor: dict, post_id: int, comment_body: str) -> None:
        if recipient_id == actor.get("id"):
            return
        actor_name = self._actor_name(actor)
        self.create(
            recipient_id,
            "post_comment",
            f"{actor_name} commented on your post",
            self._truncate(comment_body, 100),
            "chat-round-dots",
            target_url=f"{url_for('dashboard.feed')}#post-{post_id}",
            entity_type="feed_post",
            entity_id=post_id,
            actor_id=actor.get("id"),
        )

    def notify_course_access(self, *, user_id: int, course: dict, actor_id: int | None = None, title_prefix: str = "Access granted to") -> None:
        self.create(
            user_id,
            "course_access",
            f"{title_prefix} '{course['title']}'",
            "You can start learning now.",
            "book",
            target_url=url_for("courses.detail", course_id=course["id"]),
            entity_type="course",
            entity_id=course["id"],
            actor_id=actor_id,
        )

    def notify_course_access_request(self, *, admin_id: int, requester: dict, course: dict, request_id: int) -> None:
        requester_name = self._actor_name(requester)
        self.create(
            admin_id,
            "course_access_request",
            f"{requester_name} requested course access",
            course["title"],
            "shield-user",
            target_url=url_for("admin.grant_access", user_id=requester["id"]),
            entity_type="course_access_request",
            entity_id=request_id,
            actor_id=requester.get("id"),
        )

    def notify_course_request_approved(self, *, user_id: int, course: dict, actor_id: int | None = None) -> None:
        self.create(
            user_id,
            "course_request_approved",
            f"Your request was approved for '{course['title']}'",
            "You can open the course now.",
            "check-circle",
            target_url=url_for("courses.detail", course_id=course["id"]),
            entity_type="course",
            entity_id=course["id"],
            actor_id=actor_id,
        )

    def notify_course_request_rejected(self, *, user_id: int, course: dict, actor_id: int | None = None) -> None:
        self.create(
            user_id,
            "course_request_rejected",
            f"Your request was declined for '{course['title']}'",
            "You can contact the admin or try another course.",
            "close-circle",
            target_url=url_for("courses.detail", course_id=course["id"]),
            entity_type="course",
            entity_id=course["id"],
            actor_id=actor_id,
        )

    def notify_book_access(self, *, user_id: int, book: dict, actor_id: int | None = None, title_prefix: str = "Access granted to") -> None:
        self.create(
            user_id,
            "book_access",
            f"{title_prefix} '{book['title']}'",
            "You can open the book from your library now.",
            "document-text",
            target_url=url_for("library.view_book", book_id=book["id"]),
            entity_type="book",
            entity_id=book["id"],
            actor_id=actor_id,
        )

    def notify_course_published(self, *, instructor_id: int, course_id: int, title: str) -> None:
        self.create(
            instructor_id,
            "course_published",
            "Course published",
            title,
            "book-2",
            target_url=url_for("courses.detail", course_id=course_id),
            entity_type="course",
            entity_id=course_id,
            actor_id=instructor_id,
        )

    def notify_lesson_published(self, *, recipient_id: int, actor_id: int | None, course_id: int, lesson_id: int, title: str) -> None:
        self.create(
            recipient_id,
            "lesson_published",
            "New lesson available",
            title,
            "video-frame-play-horizontal",
            target_url=url_for("courses.lesson_detail", course_id=course_id, video_id=lesson_id),
            entity_type="lesson",
            entity_id=lesson_id,
            actor_id=actor_id,
        )

    def notify_book_published(self, *, uploader_id: int, book_id: int, title: str) -> None:
        self.create(
            uploader_id,
            "book_published",
            "Book added to the library",
            title,
            "document-text",
            target_url=url_for("library.view_book", book_id=book_id),
            entity_type="book",
            entity_id=book_id,
            actor_id=uploader_id,
        )

    def notify_xp_award(self, *, user_id: int, title: str, body: str) -> None:
        self.create(
            user_id,
            "xp_award",
            title,
            body,
            "bolt",
            target_url=url_for("profile.view", username=self._username_for_user(user_id)),
            entity_type="user",
            entity_id=user_id,
            actor_id=user_id,
        )

    def _username_for_user(self, user_id: int) -> str:
        user = self.fetchone("SELECT username FROM users WHERE id=?", (user_id,)) or {}
        return user.get("username", "")

    @staticmethod
    def _actor_name(actor: dict | None) -> str:
        if not actor:
            return "Someone"
        return actor.get("full_name") or actor.get("username") or "Someone"

    @staticmethod
    def _truncate(value: str | None, max_length: int) -> str:
        text = " ".join((value or "").split()).strip()
        if len(text) <= max_length:
            return text
        return text[:max_length].rstrip() + "..."

    @staticmethod
    def _format_timestamp(value: str | None) -> str:
        if not value:
            return ""
        return str(value).replace("T", " ")[:16]
