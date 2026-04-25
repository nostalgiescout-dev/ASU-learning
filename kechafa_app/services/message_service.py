from __future__ import annotations

from dataclasses import dataclass

from kechafa_app.repositories.friend_repository import FriendRepository
from kechafa_app.repositories.message_repository import MessageRepository
from kechafa_app.services.notification_service import NotificationService


@dataclass
class MessageActionResult:
    ok: bool
    thread_id: int | None = None
    error: str | None = None


class MessageService:
    def __init__(self):
        self.repo = MessageRepository()
        self.friend_repo = FriendRepository()
        self.notifications = NotificationService()

    def list_inbox(self, user_id: int) -> dict[str, list[dict]]:
        threads = []
        for thread in self.repo.list_threads_for_user(user_id):
            other_user = self.repo.get_user_summary(thread["other_id"]) if thread.get("other_id") else None
            threads.append(
                {
                    **thread,
                    "other_user": other_user,
                    "display_name": self._display_name(other_user, fallback=f"Conversation #{thread['id']}"),
                    "display_role": self._display_role(other_user.get("role") if other_user else None),
                    "last_body_preview": self._truncate(thread.get("last_body"), 60, fallback="No messages yet"),
                    "last_time_label": self._format_timestamp(thread.get("last_time")),
                    "unread_count": int(thread.get("unread_count") or 0),
                }
            )

        friends = []
        for friend in self.friend_repo.list_friends_for_user(user_id):
            friends.append(
                {
                    **friend,
                    "display_name": self._display_name(friend, fallback="Friend"),
                    "display_role": self._display_role(friend.get("role")),
                    "connected_label": self._format_timestamp(friend.get("responded_at")),
                }
            )

        suggestions = []
        for suggestion in self.friend_repo.list_friend_suggestions(user_id):
            suggestions.append(
                {
                    **suggestion,
                    "display_name": self._display_name(suggestion, fallback="User"),
                    "display_role": self._display_role(suggestion.get("role")),
                    "incoming_request": bool(suggestion.get("incoming_request")),
                }
            )

        return {
            "threads": threads,
            "friends": friends,
            "friend_suggestions": suggestions,
            "instructors": self.repo.list_instructors(),
        }

    def get_thread_view(self, user_id: int, thread_id: int) -> dict | None:
        thread = self.repo.get_thread_for_user(user_id, thread_id)
        if not thread:
            return None

        other_id = thread["participant_b"] if thread["participant_a"] == user_id else thread["participant_a"]
        other_user = self.repo.get_user_summary(other_id) if other_id else None

        messages = []
        for message in self.repo.list_thread_messages(thread_id):
            messages.append(
                {
                    **message,
                    "created_label": self._format_time_only(message.get("created_at")),
                }
            )

        self.repo.mark_thread_as_read(thread_id, user_id)
        self.notifications.mark_related_as_read(
            user_id,
            kind="message_received",
            entity_type="thread",
            entity_id=thread_id,
        )
        return {
            "thread": thread,
            "messages": messages,
            "other_user": other_user,
            "other_user_display_name": self._display_name(other_user, fallback="Conversation"),
            "other_user_role_label": self._display_role(other_user.get("role") if other_user else None),
        }

    def send_message(
        self,
        *,
        user_id: int,
        receiver_id: int | None,
        body: str,
        thread_id: int | None,
    ) -> MessageActionResult:
        cleaned_body = " ".join((body or "").split()).strip()
        if not cleaned_body:
            return MessageActionResult(ok=False, error="Message cannot be empty.")

        if thread_id:
            thread = self.repo.get_thread_for_user(user_id, thread_id)
            if not thread:
                return MessageActionResult(ok=False, error="Thread not found.")

            expected_receiver_id = thread["participant_b"] if thread["participant_a"] == user_id else thread["participant_a"]
            if receiver_id is not None and receiver_id != expected_receiver_id:
                return MessageActionResult(ok=False, error="Invalid conversation participant.")

            receiver_id = expected_receiver_id
        else:
            if receiver_id is None:
                return MessageActionResult(ok=False, error="Receiver is required.")
            if receiver_id == user_id:
                return MessageActionResult(ok=False, error="You cannot message yourself.")

            receiver = self.repo.get_user_summary(receiver_id)
            if not receiver or not receiver.get("is_active"):
                return MessageActionResult(ok=False, error="Receiver not found.")
            if not self._can_start_direct_chat(user_id, receiver):
                return MessageActionResult(ok=False, error="You can only start chats with friends or staff.")

            existing_thread = self.repo.find_direct_thread(user_id, receiver_id)
            thread_id = existing_thread["id"] if existing_thread else self.repo.create_thread(user_id, receiver_id)

        self.repo.create_message(cleaned_body, user_id, receiver_id, thread_id)
        self.repo.touch_thread(thread_id)
        sender = self.repo.get_user_summary(user_id)
        if sender and receiver_id is not None:
            self.notifications.notify_message_received(
                recipient_id=receiver_id,
                sender=sender,
                thread_id=thread_id,
                message_preview=cleaned_body,
            )
        return MessageActionResult(ok=True, thread_id=thread_id)

    def open_direct_chat(self, user_id: int, other_user_id: int) -> MessageActionResult:
        if other_user_id == user_id:
            return MessageActionResult(ok=False, error="You cannot open a chat with yourself.")

        other_user = self.repo.get_user_summary(other_user_id)
        if not other_user or not other_user.get("is_active"):
            return MessageActionResult(ok=False, error="User not found.")
        if not self._can_start_direct_chat(user_id, other_user):
            return MessageActionResult(ok=False, error="You can only chat with friends or staff.")

        existing_thread = self.repo.find_direct_thread(user_id, other_user_id)
        thread_id = existing_thread["id"] if existing_thread else self.repo.create_thread(user_id, other_user_id)
        return MessageActionResult(ok=True, thread_id=thread_id)

    def _can_start_direct_chat(self, user_id: int, other_user: dict | None) -> bool:
        if not other_user:
            return False
        if other_user.get("role") in {"admin", "instructor"}:
            return True

        friendship = self.friend_repo.get_latest_friendship(user_id, other_user["id"])
        return bool(friendship and friendship.get("status") == "accepted")

    @staticmethod
    def _display_name(user: dict | None, *, fallback: str) -> str:
        if not user:
            return fallback
        return user.get("full_name") or user.get("username") or fallback

    @staticmethod
    def _display_role(role: str | None) -> str:
        return {
            "admin": "Admin",
            "instructor": "Instructor",
            "scout": "Scout",
        }.get(role or "", "Scout")

    @staticmethod
    def _truncate(value: str | None, max_length: int, *, fallback: str) -> str:
        cleaned = " ".join((value or "").split()).strip()
        if not cleaned:
            return fallback
        return cleaned[:max_length] + ("..." if len(cleaned) > max_length else "")

    @staticmethod
    def _format_timestamp(value: str | None) -> str:
        if not value:
            return ""
        return str(value).replace("T", " ")[:16]

    @staticmethod
    def _format_time_only(value: str | None) -> str:
        text = MessageService._format_timestamp(value)
        if len(text) >= 16:
            return text[11:16]
        return text or ""
