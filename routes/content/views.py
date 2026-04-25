from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from database import execute, fetchall, fetchone
from i18n import t
from routes.auth import instructor_required, login_required

content_bp = Blueprint("content", __name__, url_prefix="/content")

UPLOAD_ROOT = Path("static") / "uploads" / "content"
ALLOWED_EXTENSIONS = {
    "video": {"mp4"},
    "reel": {"mp4"},
    "book": {"pdf"},
}

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _allowed_file(filename: str, content_type: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS[content_type]


def _serialize_video(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "type": row["video_type"],
        "media_url": row["video_url"],
        "downloadable": False,
    }


def _serialize_book(row: dict) -> dict:
    relative_path = row["file_path"].lstrip("/")
    media_url = url_for("static", filename=relative_path)
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "type": "book",
        "media_url": media_url,
        "downloadable": True,
    }


def _static_disk_path(relative_path: str) -> Path:
    return Path(current_app.static_folder) / relative_path.lstrip("/").replace("\\", "/")


def _default_book_category_id() -> int | None:
    category = fetchone(
        """
        SELECT id
        FROM book_categories
        ORDER BY CASE WHEN slug='general' THEN 0 ELSE 1 END, id
        LIMIT 1
        """
    )
    return category["id"] if category else None


def _get_contents(content_type: str):
    if content_type == "book":
        books = fetchall("SELECT * FROM books ORDER BY created_at DESC")
        return [_serialize_book(book) for book in books]

    videos = fetchall(
        "SELECT * FROM videos WHERE video_type=? AND is_published=1 ORDER BY created_at DESC",
        (content_type,),
    )
    return [_serialize_video(video) for video in videos]


@content_bp.route("/admin/upload", methods=["GET", "POST"])
@instructor_required
def upload_content():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        content_type = request.form.get("type", "video")
        file = request.files.get("file")
        lang = session.get("lang", "en")

        if content_type not in ALLOWED_EXTENSIONS:
            flash(t("Invalid file type", lang), "danger")
            return redirect(url_for("content.upload_content"))

        if not title or not file or not file.filename:
            flash(t("Please provide title", lang), "danger")
            return redirect(url_for("content.upload_content"))

        if not _allowed_file(file.filename, content_type):
            flash(t("Invalid file type", lang), "danger")
            return redirect(url_for("content.upload_content"))

        filename = secure_filename(file.filename)
        target_dir = UPLOAD_ROOT / content_type
        target_dir.mkdir(parents=True, exist_ok=True)
        save_path = target_dir / filename

        if save_path.exists():
            stem = save_path.stem
            suffix = save_path.suffix
            counter = 1
            while save_path.exists():
                save_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        file.save(save_path)
        relative_path = save_path.relative_to(Path("static")).as_posix()

        if content_type == "book":
            category_id = _default_book_category_id()
            execute(
                "INSERT INTO books (title, description, file_path, language, category_id, uploaded_by) VALUES (?,?,?,?,?,?)",
                (title, description, relative_path, session.get("lang", "en"), category_id, session["user_id"]),
            )
        else:
            execute(
                "INSERT INTO videos (title, description, video_url, video_type, category, is_published, uploader_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (title, description, url_for("static", filename=relative_path), content_type, "general", 1, session["user_id"]),
            )

        flash(t("Content uploaded successfully", lang), "success")
        return redirect(url_for("content.upload_content"))

    return render_template("content/upload.html")


@content_bp.route("/admin/delete/<string:content_type>/<int:content_id>", methods=["POST"])
@instructor_required
def delete_content(content_type: str, content_id: int):
    if content_type == "book":
        row = fetchone("SELECT * FROM books WHERE id=?", (content_id,))
        if not row:
            abort(404)
        execute("UPDATE feed_posts SET book_id=NULL WHERE book_id=?", (content_id,))
        execute("DELETE FROM book_access WHERE book_id=?", (content_id,))
        execute("DELETE FROM books WHERE id=?", (content_id,))
        disk_path = _static_disk_path(row["file_path"])
    else:
        row = fetchone("SELECT * FROM videos WHERE id=? AND video_type IN ('video', 'reel')", (content_id,))
        if not row:
            abort(404)
        execute("DELETE FROM videos WHERE id=?", (content_id,))
        local_path = row["video_url"].replace(url_for("static", filename=""), "", 1).lstrip("/")
        disk_path = _static_disk_path(local_path)

    try:
        if disk_path.exists():
            disk_path.unlink()
    except OSError:
        pass

    flash(t("Content deleted", session.get("lang", "en")), "success")
    return redirect(url_for("content.upload_content"))


@content_bp.route("/videos")
def videos():
    return render_template("content/videos.html", contents=_get_contents("video"))


@content_bp.route("/reels")
def reels():
    uid = session.get("user_id")
    reels = fetchall("""
        SELECT v.*, u.username, u.full_name, u.avatar_url, u.role,
               (SELECT COUNT(*) FROM likes WHERE video_id=v.id) as like_count,
               (SELECT COUNT(*) FROM comments WHERE video_id=v.id) as comment_count
        FROM videos v
        LEFT JOIN users u ON u.id = v.uploader_id
        WHERE v.video_type='reel' AND v.is_published=1
        ORDER BY v.created_at DESC
    """)
    if uid:
        liked_ids = {
            r["video_id"]
            for r in fetchall("SELECT video_id FROM likes WHERE user_id=?", (uid,))
        }
        reels = [dict(r, liked=(r["id"] in liked_ids)) for r in reels]
    return render_template("content/reels.html", reels=reels)


@content_bp.route("/books")
def books():
    return render_template("content/books.html", contents=_get_contents("book"))


@content_bp.route("/<string:content_type>/<int:content_id>")
def content_detail(content_type: str, content_id: int):
    if content_type == "book":
        row = fetchone("SELECT * FROM books WHERE id=?", (content_id,))
        if not row:
            abort(404)
        content = _serialize_book(row)
    else:
        row = fetchone("SELECT * FROM videos WHERE id=? AND video_type IN ('video', 'reel')", (content_id,))
        if not row:
            abort(404)
        content = _serialize_video(row)

    return render_template("content/detail.html", content=content)


@content_bp.route("/download/<string:content_type>/<int:content_id>")
@login_required
def download_content(content_type: str, content_id: int):
    if content_type != "book":
        abort(403)

    row = fetchone("SELECT * FROM books WHERE id=?", (content_id,))
    if not row:
        abort(404)

    abs_file_path = _static_disk_path(row["file_path"])
    if not abs_file_path.is_file():
        abort(404)

    return send_from_directory(abs_file_path.parent, abs_file_path.name, as_attachment=True)
