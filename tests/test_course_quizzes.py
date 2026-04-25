from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import database
from database import execute, fetchall, fetchone, init_db
from routes.courses import _quiz_payloads_from_form, _validate_quiz_payloads
from werkzeug.datastructures import MultiDict


class CourseQuizSupportTest(unittest.TestCase):
    def setUp(self) -> None:
        self._original_db_path = database.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        self._print_patch = patch("builtins.print")
        self._print_patch.start()
        database.DB_PATH = str(Path(self._temp_dir.name) / "course-quiz-test.db")
        init_db()

    def tearDown(self) -> None:
        database.DB_PATH = self._original_db_path
        self._print_patch.stop()
        self._temp_dir.cleanup()

    def test_quiz_payloads_from_form_support_multiple_questions(self):
        form = MultiDict([
            ("quiz_question[]", "What is CPR?"),
            ("quiz_option_a[]", "Cardio Pulmonary Resuscitation"),
            ("quiz_option_b[]", "Camp Patrol Rules"),
            ("quiz_option_c[]", ""),
            ("quiz_option_d[]", ""),
            ("quiz_correct_option[]", "A"),
            ("quiz_explanation[]", "It is emergency first aid."),
            ("quiz_question[]", "Which knot is best for a fixed loop?"),
            ("quiz_option_a[]", "Clove hitch"),
            ("quiz_option_b[]", "Bowline"),
            ("quiz_option_c[]", ""),
            ("quiz_option_d[]", ""),
            ("quiz_correct_option[]", "b"),
            ("quiz_explanation[]", "Bowline creates a fixed loop."),
        ])

        quizzes = _quiz_payloads_from_form(form)

        self.assertEqual(2, len(quizzes))
        self.assertEqual("a", quizzes[0]["quiz_correct_option"])
        self.assertEqual("Which knot is best for a fixed loop?", quizzes[1]["quiz_question"])

    def test_validate_quiz_payloads_prefixes_question_number(self):
        quizzes = [
            {
                "quiz_question": "Incomplete question",
                "quiz_option_a": "",
                "quiz_option_b": "",
                "quiz_option_c": "",
                "quiz_option_d": "",
                "quiz_correct_option": "",
                "quiz_explanation": "",
            }
        ]

        errors = _validate_quiz_payloads(quizzes)

        self.assertIn(
            "Quiz question 1: Quiz options A and B are required when adding a quiz.",
            errors,
        )

    def test_init_db_backfills_legacy_lesson_quiz_into_multi_question_table(self):
        instructor = fetchone("SELECT id FROM users WHERE username='lead_instructor'")
        course = fetchone("SELECT id, category FROM courses ORDER BY id LIMIT 1")

        lesson_id = execute(
            """
            INSERT INTO videos (
                title, description, video_url, thumbnail_url, video_type, category, duration_secs,
                order_index, xp_reward, is_published, uploader_id, course_id,
                quiz_question, quiz_option_a, quiz_option_b, quiz_option_c, quiz_option_d,
                quiz_correct_option, quiz_explanation
            )
            VALUES (?, ?, ?, ?, 'lesson', ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Legacy quiz lesson",
                "Lesson saved with the old single-question fields.",
                "https://example.com/video.mp4",
                "",
                course["category"],
                120,
                99,
                50,
                instructor["id"],
                course["id"],
                "What should you check first?",
                "Scene safety",
                "Your backpack",
                "",
                "",
                "a",
                "Always check the scene before helping.",
            ),
        )

        init_db()

        quiz_rows = fetchall(
            "SELECT lesson_id, question_text, correct_option FROM lesson_quiz_questions WHERE lesson_id=?",
            (lesson_id,),
        )

        self.assertEqual(1, len(quiz_rows))
        self.assertEqual(lesson_id, quiz_rows[0]["lesson_id"])
        self.assertEqual("What should you check first?", quiz_rows[0]["question_text"])
        self.assertEqual("a", quiz_rows[0]["correct_option"])


if __name__ == "__main__":
    unittest.main()
