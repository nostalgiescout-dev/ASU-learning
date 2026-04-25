from __future__ import annotations

import database
from database import execute, fetchone, init_db
from kechafa_app.services.message_service import MessageService


def _build_service(tmp_path, monkeypatch) -> MessageService:
    db_path = tmp_path / "messages-test.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    init_db()
    return MessageService()


def test_send_message_creates_thread_and_marks_reads(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    scout = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    instructor = fetchone("SELECT id FROM users WHERE username='lead_instructor'")

    result = service.send_message(
        user_id=scout["id"],
        receiver_id=instructor["id"],
        body="  Hello instructor  ",
        thread_id=None,
    )

    assert result.ok is True
    assert result.thread_id is not None

    inbox_before_open = service.list_inbox(instructor["id"])
    assert inbox_before_open["threads"][0]["unread_count"] == 1
    assert inbox_before_open["threads"][0]["display_name"] == "Sara Benali"

    thread_view = service.get_thread_view(instructor["id"], result.thread_id)
    assert thread_view is not None
    assert thread_view["messages"][0]["body"] == "Hello instructor"
    assert isinstance(thread_view["messages"][0]["created_label"], str)

    inbox_after_open = service.list_inbox(instructor["id"])
    assert inbox_after_open["threads"][0]["unread_count"] == 0


def test_send_message_rejects_thread_hijack(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    admin = fetchone("SELECT id FROM users WHERE username='kechafa_admin'")
    scout = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    instructor = fetchone("SELECT id FROM users WHERE username='lead_instructor'")

    protected_thread = service.send_message(
        user_id=admin["id"],
        receiver_id=instructor["id"],
        body="Private admin message",
        thread_id=None,
    )
    assert protected_thread.ok is True

    hijack_attempt = service.send_message(
        user_id=scout["id"],
        receiver_id=instructor["id"],
        body="I should not be able to post here",
        thread_id=protected_thread.thread_id,
    )

    assert hijack_attempt.ok is False
    assert hijack_attempt.error == "Thread not found."


def test_send_message_rejects_wrong_receiver_for_thread(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    admin = fetchone("SELECT id FROM users WHERE username='kechafa_admin'")
    scout = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    instructor = fetchone("SELECT id FROM users WHERE username='lead_instructor'")

    thread = service.send_message(
        user_id=scout["id"],
        receiver_id=instructor["id"],
        body="Hello again",
        thread_id=None,
    )
    assert thread.ok is True

    wrong_receiver_attempt = service.send_message(
        user_id=scout["id"],
        receiver_id=admin["id"],
        body="This should fail",
        thread_id=thread.thread_id,
    )

    assert wrong_receiver_attempt.ok is False
    assert wrong_receiver_attempt.error == "Invalid conversation participant."


def test_list_inbox_includes_accepted_friends_and_suggestions(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    scout = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    admin = fetchone("SELECT id FROM users WHERE username='kechafa_admin'")

    new_friend_id = execute(
        """
        INSERT INTO users (
            username, email, password_hash, full_name, role, preferred_lang, scout_unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("friend_omar", "omar@kechafa.ma", "hash", "Omar Alaoui", "scout", "en", "Tangier Group 1"),
    )
    stranger_id = execute(
        """
        INSERT INTO users (
            username, email, password_hash, full_name, role, preferred_lang, scout_unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("stranger_lina", "lina@kechafa.ma", "hash", "Lina Idrissi", "scout", "en", "Fes Group 2"),
    )

    execute(
        """
        INSERT INTO friend_requests (sender_id, receiver_id, status, responded_at)
        VALUES (?, ?, 'accepted', datetime('now'))
        """,
        (scout["id"], new_friend_id),
    )
    execute(
        """
        INSERT INTO friend_requests (sender_id, receiver_id, status)
        VALUES (?, ?, 'pending')
        """,
        (stranger_id, scout["id"]),
    )

    inbox = service.list_inbox(scout["id"])

    friend_names = {item["display_name"] for item in inbox["friends"]}
    assert "Omar Alaoui" in friend_names

    accepted_suggestion = next(item for item in inbox["friend_suggestions"] if item["id"] == new_friend_id)
    assert accepted_suggestion["friend_status"] == "accepted"

    incoming_suggestion = next(item for item in inbox["friend_suggestions"] if item["id"] == stranger_id)
    assert incoming_suggestion["incoming_request"] is True

    admin_suggestion = next(item for item in inbox["friend_suggestions"] if item["id"] == admin["id"])
    assert admin_suggestion["display_role"] == "Admin"


def test_open_direct_chat_requires_friend_or_instructor(tmp_path, monkeypatch):
    service = _build_service(tmp_path, monkeypatch)
    scout = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    instructor = fetchone("SELECT id FROM users WHERE username='lead_instructor'")

    friend_id = execute(
        """
        INSERT INTO users (
            username, email, password_hash, full_name, role, preferred_lang, scout_unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("friend_yassine", "yassine@kechafa.ma", "hash", "Yassine B", "scout", "en", "Agadir Group"),
    )
    stranger_id = execute(
        """
        INSERT INTO users (
            username, email, password_hash, full_name, role, preferred_lang, scout_unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("stranger_nadia", "nadia@kechafa.ma", "hash", "Nadia H", "scout", "en", "Meknes Group"),
    )
    execute(
        """
        INSERT INTO friend_requests (sender_id, receiver_id, status, responded_at)
        VALUES (?, ?, 'accepted', datetime('now'))
        """,
        (scout["id"], friend_id),
    )

    friend_chat = service.open_direct_chat(scout["id"], friend_id)
    assert friend_chat.ok is True
    assert friend_chat.thread_id is not None

    repeat_friend_chat = service.open_direct_chat(scout["id"], friend_id)
    assert repeat_friend_chat.ok is True
    assert repeat_friend_chat.thread_id == friend_chat.thread_id

    instructor_chat = service.open_direct_chat(scout["id"], instructor["id"])
    assert instructor_chat.ok is True

    stranger_chat = service.open_direct_chat(scout["id"], stranger_id)
    assert stranger_chat.ok is False
    assert stranger_chat.error == "You can only chat with friends or staff."
