import database
from database import execute, fetchone
from kechafa_app import create_app


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "feed-comments.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    return create_app(config_overrides={"TESTING": True, "KECHAFA_DB": str(db_path)})


def test_user_can_update_own_feed_comment(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    user = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    assert user is not None

    post_id = execute(
        """
        INSERT INTO feed_posts (author_id, post_type, title, body, category, is_published)
        VALUES (?, 'text', ?, ?, 'community', 1)
        """,
        (user["id"], "Comment edit test", "Initial post body"),
    )
    comment_id = execute(
        "INSERT INTO post_comments (post_id, author_id, body) VALUES (?, ?, ?)",
        (post_id, user["id"], "Old comment"),
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = user["id"]

        response = client.post(
            f"/feed/posts/{post_id}/comment/{comment_id}/update",
            data={"body": "New comment", "feed_filter": "all", "page": "1"},
        )

    assert response.status_code == 302
    row = fetchone("SELECT body FROM post_comments WHERE id=?", (comment_id,))
    assert row["body"] == "New comment"


def test_user_cannot_update_someone_elses_feed_comment(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    author = fetchone("SELECT id FROM users WHERE username='kechafa_admin'")
    other_user = fetchone("SELECT id FROM users WHERE username='scout_sara'")
    assert author is not None
    assert other_user is not None

    post_id = execute(
        """
        INSERT INTO feed_posts (author_id, post_type, title, body, category, is_published)
        VALUES (?, 'text', ?, ?, 'community', 1)
        """,
        (author["id"], "Permission test", "Initial post body"),
    )
    comment_id = execute(
        "INSERT INTO post_comments (post_id, author_id, body) VALUES (?, ?, ?)",
        (post_id, author["id"], "Admin comment"),
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = other_user["id"]

        response = client.post(
            f"/feed/posts/{post_id}/comment/{comment_id}/update",
            data={"body": "Hacked", "feed_filter": "all", "page": "1"},
        )

    assert response.status_code == 302
    row = fetchone("SELECT body FROM post_comments WHERE id=?", (comment_id,))
    assert row["body"] == "Admin comment"

