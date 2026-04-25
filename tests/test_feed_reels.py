import unittest

from database import execute, fetchone
from kechafa_app import create_app


class FeedReelsViewTest(unittest.TestCase):
    def test_reel_filter_renders_immersive_viewer(self):
        app = create_app(config_overrides={"TESTING": True})
        user = fetchone(
            "SELECT id FROM users ORDER BY CASE WHEN role='admin' THEN 0 ELSE 1 END, id LIMIT 1"
        )
        self.assertIsNotNone(user)

        post_id = execute(
            """
            INSERT INTO feed_posts (author_id, post_type, title, body, media_url, category, is_published)
            VALUES (?, 'reel', ?, ?, ?, 'community', 1)
            """,
            (
                user["id"],
                "Viewer test reel",
                "Temporary reel used to verify the reels viewer.",
                "/static/uploads/content/feed/video/test-reel.mp4",
            ),
        )

        try:
            with app.test_client() as client:
                with client.session_transaction() as session:
                    session["user_id"] = user["id"]

                response = client.get("/feed?filter=reel")
                text = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("reel-viewer-shell", text)
            self.assertIn(f"reel-post-{post_id}", text)
            self.assertIn("reel-nav-next", text)
            self.assertIn("reel-toggle-mute", text)
        finally:
            execute("DELETE FROM feed_posts WHERE id=?", (post_id,))


if __name__ == "__main__":
    unittest.main()
