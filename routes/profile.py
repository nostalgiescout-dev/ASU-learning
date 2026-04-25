"""routes/profile.py"""
import base64
import os
import re
import uuid

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from werkzeug.utils import secure_filename

from database import fetchone, fetchall, execute
from kechafa_app.core.security import can_publish_feed_posts, is_admin_like_user
from routes.auth import login_required

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

@profile_bp.route("/<username>")
@login_required
def view(username):
    user = fetchone("SELECT * FROM users WHERE username=?", (username,))
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("dashboard.feed"))
    viewer = fetchone("SELECT id, role, username FROM users WHERE id=?", (session["user_id"],)) or {}
    badges = fetchall(
        "SELECT ub.awarded_at, b.* FROM user_badges ub JOIN badges b ON ub.badge_id=b.id WHERE ub.user_id=?",
        (user["id"],))
    enrollments = fetchall(
        "SELECT e.*, c.title, c.category FROM enrollments e JOIN courses c ON e.course_id=c.id "
        "WHERE e.user_id=? ORDER BY e.enrolled_at DESC LIMIT 6", (user["id"],))
    recent_videos = fetchall(
        "SELECT * FROM videos WHERE uploader_id=? AND is_published=1 ORDER BY created_at DESC LIMIT 6",
        (user["id"],))
    user_posts = fetchall(
        """
        SELECT
            fp.*,
            (
                SELECT COUNT(*) FROM post_likes pl
                WHERE pl.post_id = fp.id
            ) AS like_count,
            (
                SELECT COUNT(*) FROM post_comments pc
                WHERE pc.post_id = fp.id
            ) AS comment_count,
            (
                SELECT COUNT(*) FROM post_shares ps
                WHERE ps.post_id = fp.id
            ) AS share_count
        FROM feed_posts fp
        WHERE fp.author_id=?
          AND fp.is_published=1
          AND fp.post_type IN ('text', 'video', 'reel')
        ORDER BY fp.created_at DESC
        LIMIT 8
        """,
        (user["id"],),
    )
    if is_admin_like_user(viewer):
        recent_books = fetchall(
            """
            SELECT b.*, c.name AS category_name
            FROM books b
            LEFT JOIN book_categories c ON c.id = b.category_id
            WHERE b.uploaded_by=?
            ORDER BY b.created_at DESC
            LIMIT 4
            """,
            (user["id"],),
        )
    else:
        recent_books = fetchall(
            """
            SELECT b.*, c.name AS category_name
            FROM books b
            LEFT JOIN book_categories c ON c.id = b.category_id
            WHERE b.uploaded_by=?
              AND (
                b.uploaded_by=?
                OR EXISTS (
                    SELECT 1
                    FROM book_access ba
                    WHERE ba.book_id=b.id AND ba.user_id=?
                )
              )
            ORDER BY b.created_at DESC
            LIMIT 4
            """,
            (user["id"], session["user_id"], session["user_id"]),
        )
    prog = user["level_points"] % 1000 / 1000
    can_publish_posts = session["user_id"] == user["id"] and can_publish_feed_posts(viewer)
    return render_template("profile/view.html",
        profile_user=user, badges=badges, enrollments=enrollments,
        recent_videos=recent_videos, recent_books=recent_books, progress=prog,
        user_posts=user_posts, can_publish_posts=can_publish_posts)


@profile_bp.route("/edit", methods=["GET","POST"])
@login_required
def edit():
    uid = session["user_id"]
    if request.method == "POST":
        execute(
            "UPDATE users SET full_name=?,bio=?,country=?,scout_unit=?,avatar_url=?,preferred_lang=? WHERE id=?",
            (request.form.get("full_name",""),
             request.form.get("bio",""),
             request.form.get("country",""),
             request.form.get("scout_unit",""),
             request.form.get("avatar_url",""),
             request.form.get("preferred_lang","en"),
             uid))
        lang = request.form.get("preferred_lang","en")
        session["lang"] = lang
        flash("Profile updated! ✅", "success")
        user = fetchone("SELECT username FROM users WHERE id=?", (uid,))
        return redirect(url_for("profile.view", username=user["username"]))
    user = fetchone("SELECT * FROM users WHERE id=?", (uid,))
    return render_template("profile/edit.html", user=user)


def _save_avatar_file(user_id: int, data: bytes, ext: str) -> str:
    uploads_path = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "avatars")
    uploads_path = os.path.abspath(uploads_path)
    os.makedirs(uploads_path, exist_ok=True)

    filename = f"avatar_{user_id}_{uuid.uuid4().hex}.{ext}"
    filename = secure_filename(filename)
    file_path = os.path.join(uploads_path, filename)

    with open(file_path, "wb") as f:
        f.write(data)

    return url_for("static", filename=f"uploads/avatars/{filename}")


@profile_bp.route("/upload-avatar", methods=["POST"])
@login_required
def upload_avatar():
    uid = session["user_id"]

    # Accept either a file upload or a base64 payload (from in-browser crop)
    file = request.files.get("avatar")
    data_url = request.form.get("avatar_data")

    if file and file.filename:
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            return jsonify(success=False, error="Unsupported file type."), 400
        raw = file.read()
    elif data_url:
        match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", data_url)
        if not match:
            return jsonify(success=False, error="Invalid image data."), 400
        ext = match.group(1)
        raw = base64.b64decode(match.group(2))
    else:
        return jsonify(success=False, error="No image provided."), 400

    if len(raw) > 5 * 1024 * 1024:
        return jsonify(success=False, error="Image must be 5MB or smaller."), 400

    try:
        url = _save_avatar_file(uid, raw, ext if ext != 'jpeg' else 'jpg')
        # Persist to user record
        execute("UPDATE users SET avatar_url=? WHERE id=?", (url, uid))
        return jsonify(success=True, url=url)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
