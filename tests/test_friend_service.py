from __future__ import annotations

import database
from database import execute, fetchone, init_db
from kechafa_app.services.friend_service import FriendService


def _build_service(tmp_path, monkeypatch) -> FriendService:
    db_path = tmp_path / "friends-test.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    init_db()
    return FriendService()


def test_send_friend_request_creates_pending_request_and_notification(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    sender = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    receiver = fetchone("SELECT id FROM users WHERE username='kechafa_admin'")

    result = service.send_or_accept_request(sender["id"], receiver["id"])

    assert result.ok is True
    assert result.status == "pending"
    assert result.label == "Pending"

    friendship = fetchone(
        "SELECT status FROM friend_requests WHERE sender_id=? AND receiver_id=? ORDER BY id DESC LIMIT 1",
        (sender["id"], receiver["id"]),
    )
    assert friendship["status"] == "pending"

    notification = fetchone(
        "SELECT kind, title FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (receiver["id"],),
    )
    assert notification["kind"] == "friend_request"
    assert notification["title"] == "New friend request"


def test_send_friend_request_accepts_incoming_pending_request(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    sender = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    receiver = fetchone("SELECT id FROM users WHERE username='kechafa_admin'")

    execute(
        "INSERT INTO friend_requests (sender_id, receiver_id, status) VALUES (?, ?, 'pending')",
        (receiver["id"], sender["id"]),
    )

    result = service.send_or_accept_request(sender["id"], receiver["id"])

    assert result.ok is True
    assert result.status == "accepted"
    assert result.label == "Friends"

    friendship = fetchone(
        "SELECT status, responded_at FROM friend_requests WHERE sender_id=? AND receiver_id=? ORDER BY id DESC LIMIT 1",
        (receiver["id"], sender["id"]),
    )
    assert friendship["status"] == "accepted"
    assert friendship["responded_at"] is not None

    notification = fetchone(
        "SELECT kind, title FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (receiver["id"],),
    )
    assert notification["kind"] == "friend_accept"
    assert notification["title"] == "Friend request accepted"


def test_send_friend_request_rejects_self_request(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    sender = fetchone("SELECT id FROM users WHERE username='scout_sara'")

    result = service.send_or_accept_request(sender["id"], sender["id"])

    assert result.ok is False
    assert result.status_code == 400
    assert result.error == "You cannot add yourself."
