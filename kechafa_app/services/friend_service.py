from __future__ import annotations

from dataclasses import dataclass

from kechafa_app.repositories.friend_repository import FriendRepository
from kechafa_app.services.notification_service import NotificationService


@dataclass
class FriendRequestResult:
    ok: bool
    status: str | None = None
    label: str | None = None
    message: str | None = None
    error: str | None = None
    status_code: int = 200


class FriendService:
    def __init__(self):
        self.repo = FriendRepository()
        self.notifications = NotificationService()

    def send_or_accept_request(self, sender_id: int, receiver_id: int) -> FriendRequestResult:
        if receiver_id == sender_id:
            return FriendRequestResult(ok=False, error="You cannot add yourself.", status_code=400)

        receiver = self.repo.get_user_summary(receiver_id)
        if not receiver:
            return FriendRequestResult(ok=False, error="User not found.", status_code=404)

        sender = self.repo.get_user_summary(sender_id) or {}
        sender_name = sender.get("full_name") or sender.get("username") or "A user"
        existing = self.repo.get_latest_friendship(sender_id, receiver_id)

        if existing and existing.get("status") == "accepted":
            return FriendRequestResult(
                ok=True,
                status="accepted",
                label="Friends",
                message="You are already friends.",
            )

        if existing and existing.get("status") == "pending":
            if existing.get("sender_id") == sender_id:
                return FriendRequestResult(
                    ok=True,
                    status="pending",
                    label="Pending",
                    message="Friend request already sent.",
                )

            self.repo.accept_request(existing["id"])
            self.notifications.create(
                receiver_id,
                "friend_accept",
                "Friend request accepted",
                f"{sender_name} accepted your request.",
                "handshake",
                target_url=f"/messages/direct/{sender_id}",
                entity_type="friendship",
                entity_id=existing["id"],
                actor_id=sender_id,
            )
            return FriendRequestResult(
                ok=True,
                status="accepted",
                label="Friends",
                message="Friend request accepted.",
            )

        self.repo.create_request(sender_id, receiver_id)
        self.notifications.create(
            receiver_id,
            "friend_request",
            "New friend request",
            f"{sender_name} wants to connect with you.",
            "handshake",
            target_url=f"/messages/direct/{sender_id}",
            entity_type="friendship",
            entity_id=None,
            actor_id=sender_id,
        )
        return FriendRequestResult(
            ok=True,
            status="pending",
            label="Pending",
            message="Friend request sent.",
        )
