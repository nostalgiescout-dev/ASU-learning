"""routes/admin.py"""
import subprocess
from pathlib import Path

from flask import Blueprint, current_app, render_template, request, jsonify, redirect, url_for, flash, session

from database import fetchone, fetchall, execute, db as db_session
from routes.auth import admin_like_required, admin_required
from kechafa_app.services.auth_service import AuthService
from kechafa_app.services.notification_service import NotificationService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
auth_service = AuthService()
notification_service = NotificationService()


def _clean_search(value: str | None) -> str:
    return (value or "").strip()


def _redirect_to_access(user_id: int | None, user_q: str = "", course_q: str = "", book_q: str = ""):
    params = {}
    if user_id:
        params["user_id"] = user_id
    if user_q:
        params["user_q"] = user_q
    if course_q:
        params["course_q"] = course_q
    if book_q:
        params["book_q"] = book_q
    return redirect(url_for("admin.grant_access", **params))


def _selected_ids(values: list[str]) -> list[int]:
    ids: list[int] = []
    for value in values:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def _delete_local_feed_media(media_url: str | None) -> None:
    if not media_url:
        return

    static_prefix = url_for("static", filename="")
    if not media_url.startswith(static_prefix):
        return

    relative_path = media_url.replace(static_prefix, "", 1).lstrip("/")
    disk_path = Path(current_app.static_folder) / relative_path
    try:
        if disk_path.exists():
            disk_path.unlink()
    except OSError:
        pass


def _cleanup_user_records(user_id: int, replacement_user_id: int) -> list[str]:
    owned_feed_media = fetchall("SELECT media_url FROM feed_posts WHERE author_id=?", (user_id,))

    with db_session() as conn:
        conn.execute("UPDATE course_categories SET created_by=? WHERE created_by=?", (replacement_user_id, user_id))
        conn.execute("UPDATE book_categories SET created_by=? WHERE created_by=?", (replacement_user_id, user_id))
        conn.execute("UPDATE books SET uploaded_by=? WHERE uploaded_by=?", (replacement_user_id, user_id))
        conn.execute("UPDATE videos SET uploader_id=? WHERE uploader_id=?", (replacement_user_id, user_id))
        conn.execute("UPDATE courses SET instructor_id=? WHERE instructor_id=?", (replacement_user_id, user_id))
        conn.execute("UPDATE community_groups SET owner_id=? WHERE owner_id=?", (replacement_user_id, user_id))
        conn.execute("UPDATE enrollments SET granted_by=NULL WHERE granted_by=?", (user_id,))
        conn.execute("UPDATE book_access SET granted_by=NULL WHERE granted_by=?", (user_id,))
        conn.execute("UPDATE course_access_requests SET responded_by=NULL WHERE responded_by=?", (user_id,))
        conn.execute("UPDATE notifications SET actor_id=NULL WHERE actor_id=?", (user_id,))
        conn.execute("UPDATE post_shares SET user_id=NULL WHERE user_id=?", (user_id,))

        conn.execute("DELETE FROM ai_conversations WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM user_badges WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM group_members WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM friend_requests WHERE sender_id=? OR receiver_id=?", (user_id, user_id))
        conn.execute("DELETE FROM messages WHERE sender_id=? OR receiver_id=?", (user_id, user_id))
        conn.execute("DELETE FROM threads WHERE participant_a=? OR participant_b=?", (user_id, user_id))
        conn.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM course_access_requests WHERE requester_id=?", (user_id,))
        conn.execute("DELETE FROM book_access WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM lesson_completions WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM enrollments WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM comments WHERE author_id=?", (user_id,))
        conn.execute("DELETE FROM likes WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM post_likes WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM post_comments WHERE author_id=?", (user_id,))

        conn.execute(
            "DELETE FROM post_likes WHERE post_id IN (SELECT id FROM feed_posts WHERE author_id=?)",
            (user_id,),
        )
        conn.execute(
            "DELETE FROM post_comments WHERE post_id IN (SELECT id FROM feed_posts WHERE author_id=?)",
            (user_id,),
        )
        conn.execute(
            "DELETE FROM post_shares WHERE post_id IN (SELECT id FROM feed_posts WHERE author_id=?)",
            (user_id,),
        )
        conn.execute("DELETE FROM feed_posts WHERE author_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))

    return [row["media_url"] for row in owned_feed_media if row.get("media_url")]


@admin_bp.route("/deploy", methods=["POST"])
@admin_required
def deploy():
    try:
        pull = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd="/var/www/ASU-learning",
            capture_output=True, text=True, timeout=60
        )
        subprocess.Popen(["systemctl", "restart", "kechafa"])
        output = pull.stdout.strip() or pull.stderr.strip()
        flash(f"✅ Deploy done: {output}", "success")
    except Exception as e:
        flash(f"❌ Deploy failed: {e}", "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/")
@admin_required
def dashboard():
    stats = {
        "users":       (fetchone("SELECT COUNT(*) as c FROM users") or {}).get("c", 0),
        "courses":     (fetchone("SELECT COUNT(*) as c FROM courses") or {}).get("c", 0),
        "videos":      (fetchone("SELECT COUNT(*) as c FROM videos") or {}).get("c", 0),
        "enrollments": (fetchone("SELECT COUNT(*) as c FROM enrollments") or {}).get("c", 0),
    }
    recent_users = fetchall("SELECT * FROM users ORDER BY created_at DESC LIMIT 10")
    return render_template("dashboard/admin.html", stats=stats, recent_users=recent_users)


@admin_bp.route("/users")
@admin_like_required
def users():
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 20
    offset = (page - 1) * per_page
    total = (fetchone("SELECT COUNT(*) as c FROM users") or {}).get("c", 0)
    users_list = fetchall("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?", (per_page, offset))
    return render_template(
        "dashboard/admin_users.html",
        users=users_list,
        page=page,
        total_pages=max(1, (total + per_page - 1) // per_page),
    )


@admin_bp.route("/access", methods=["GET", "POST"])
@admin_like_required
def grant_access():
    notification_service.mark_related_as_read(session["user_id"], kind="course_access_request")
    selected_user_id = request.args.get("user_id", type=int)
    user_q = _clean_search(request.args.get("user_q"))
    course_q = _clean_search(request.args.get("course_q"))
    book_q = _clean_search(request.args.get("book_q"))

    if request.method == "POST":
        action = request.form.get("action", "").strip()
        selected_user_id = request.form.get("user_id", type=int)
        user_q = _clean_search(request.form.get("user_q"))
        course_q = _clean_search(request.form.get("course_q"))
        book_q = _clean_search(request.form.get("book_q"))
        user = fetchone("SELECT * FROM users WHERE id=?", (selected_user_id,))
        if not user:
            flash("User not found.", "danger")
            return _redirect_to_access(None, user_q, course_q, book_q)

        if action == "grant_course":
            course_id = request.form.get("course_id", type=int)
            course = fetchone("SELECT * FROM courses WHERE id=?", (course_id,))
            if not course:
                flash("Course not found.", "danger")
            elif fetchone("SELECT id FROM enrollments WHERE user_id=? AND course_id=?", (selected_user_id, course_id)):
                flash("User already has access to this course.", "info")
            else:
                execute(
                    "INSERT INTO enrollments (user_id,course_id,granted_by) VALUES (?,?,?)",
                    (selected_user_id, course_id, session["user_id"]),
                )
                notification_service.notify_course_access(
                    user_id=selected_user_id,
                    course=course,
                    actor_id=session["user_id"],
                )
                flash("Course access granted.", "success")

        elif action == "bulk_grant_courses":
            course_ids = _selected_ids(request.form.getlist("course_ids"))
            if not course_ids:
                flash("Select at least one course to grant.", "warning")
            else:
                granted_count = 0
                placeholders = ",".join("?" for _ in course_ids)
                courses = {
                    row["id"]: row
                    for row in fetchall(
                        f"SELECT id, title FROM courses WHERE id IN ({placeholders})",
                        tuple(course_ids),
                    )
                }
                for course_id in course_ids:
                    course = courses.get(course_id)
                    if not course:
                        continue
                    if fetchone("SELECT id FROM enrollments WHERE user_id=? AND course_id=?", (selected_user_id, course_id)):
                        continue
                    execute(
                        "INSERT INTO enrollments (user_id,course_id,granted_by) VALUES (?,?,?)",
                        (selected_user_id, course_id, session["user_id"]),
                    )
                    notification_service.notify_course_access(
                        user_id=selected_user_id,
                        course=course,
                        actor_id=session["user_id"],
                    )
                    granted_count += 1
                flash(
                    "Course access granted." if granted_count == 1 else f"Course access granted for {granted_count} courses.",
                    "success" if granted_count else "info",
                )

        elif action == "revoke_course":
            course_id = request.form.get("course_id", type=int)
            execute("DELETE FROM lesson_completions WHERE user_id=? AND course_id=?", (selected_user_id, course_id))
            execute("DELETE FROM enrollments WHERE user_id=? AND course_id=?", (selected_user_id, course_id))
            flash("Course access removed.", "success")

        elif action == "grant_book":
            book_id = request.form.get("book_id", type=int)
            book = fetchone("SELECT * FROM books WHERE id=?", (book_id,))
            if not book:
                flash("Book not found.", "danger")
            elif fetchone("SELECT id FROM book_access WHERE user_id=? AND book_id=?", (selected_user_id, book_id)):
                flash("User already has access to this book.", "info")
            else:
                execute(
                    "INSERT INTO book_access (user_id, book_id, granted_by) VALUES (?, ?, ?)",
                    (selected_user_id, book_id, session["user_id"]),
                )
                notification_service.notify_book_access(
                    user_id=selected_user_id,
                    book=book,
                    actor_id=session["user_id"],
                )
                flash("Book access granted.", "success")

        elif action == "bulk_grant_books":
            book_ids = _selected_ids(request.form.getlist("book_ids"))
            if not book_ids:
                flash("Select at least one book to grant.", "warning")
            else:
                granted_count = 0
                placeholders = ",".join("?" for _ in book_ids)
                books = {
                    row["id"]: row
                    for row in fetchall(
                        f"SELECT id, title FROM books WHERE id IN ({placeholders})",
                        tuple(book_ids),
                    )
                }
                for book_id in book_ids:
                    book = books.get(book_id)
                    if not book:
                        continue
                    if fetchone("SELECT id FROM book_access WHERE user_id=? AND book_id=?", (selected_user_id, book_id)):
                        continue
                    execute(
                        "INSERT INTO book_access (user_id, book_id, granted_by) VALUES (?, ?, ?)",
                        (selected_user_id, book_id, session["user_id"]),
                    )
                    notification_service.notify_book_access(
                        user_id=selected_user_id,
                        book=book,
                        actor_id=session["user_id"],
                    )
                    granted_count += 1
                flash(
                    "Book access granted." if granted_count == 1 else f"Book access granted for {granted_count} books.",
                    "success" if granted_count else "info",
                )

        elif action == "revoke_book":
            book_id = request.form.get("book_id", type=int)
            execute("DELETE FROM book_access WHERE user_id=? AND book_id=?", (selected_user_id, book_id))
            flash("Book access removed.", "success")

        elif action == "approve_course_request":
            request_id = request.form.get("request_id", type=int)
            course_request = fetchone(
                """
                SELECT car.*, c.title
                FROM course_access_requests car
                JOIN courses c ON c.id = car.course_id
                WHERE car.id=? AND car.status='pending'
                """,
                (request_id,),
            )
            if not course_request:
                flash("Request not found.", "warning")
            elif fetchone(
                "SELECT id FROM enrollments WHERE user_id=? AND course_id=?",
                (course_request["requester_id"], course_request["course_id"]),
            ):
                execute(
                    "UPDATE course_access_requests SET status='approved', responded_by=?, responded_at=datetime('now') WHERE id=?",
                    (session["user_id"], request_id),
                )
                flash("User already had access. Request marked approved.", "info")
            else:
                execute(
                    "INSERT INTO enrollments (user_id,course_id,granted_by) VALUES (?,?,?)",
                    (course_request["requester_id"], course_request["course_id"], session["user_id"]),
                )
                execute(
                    "UPDATE course_access_requests SET status='approved', responded_by=?, responded_at=datetime('now') WHERE id=?",
                    (session["user_id"], request_id),
                )
                course = {"id": course_request["course_id"], "title": course_request["title"]}
                notification_service.notify_course_request_approved(
                    user_id=course_request["requester_id"],
                    course=course,
                    actor_id=session["user_id"],
                )
                flash("Course request approved.", "success")

        elif action == "reject_course_request":
            request_id = request.form.get("request_id", type=int)
            course_request = fetchone(
                """
                SELECT car.*, c.title
                FROM course_access_requests car
                JOIN courses c ON c.id = car.course_id
                WHERE car.id=? AND car.status='pending'
                """,
                (request_id,),
            )
            if not course_request:
                flash("Request not found.", "warning")
            else:
                execute(
                    "UPDATE course_access_requests SET status='rejected', responded_by=?, responded_at=datetime('now') WHERE id=?",
                    (session["user_id"], request_id),
                )
                course = {"id": course_request["course_id"], "title": course_request["title"]}
                notification_service.notify_course_request_rejected(
                    user_id=course_request["requester_id"],
                    course=course,
                    actor_id=session["user_id"],
                )
                flash("Course request rejected.", "success")

        return _redirect_to_access(selected_user_id, user_q, course_q, book_q)

    users_sql = "SELECT id, username, full_name, email, role, is_active FROM users"
    user_params: list[str] = []
    if user_q:
        user_like = f"%{user_q}%"
        users_sql += " WHERE username LIKE ? OR full_name LIKE ? OR email LIKE ?"
        user_params.extend([user_like, user_like, user_like])
    users_sql += " ORDER BY full_name COLLATE NOCASE, username COLLATE NOCASE"
    users_list = fetchall(users_sql, tuple(user_params))
    selected_user = fetchone("SELECT * FROM users WHERE id=?", (selected_user_id,)) if selected_user_id else None

    assigned_courses = []
    available_courses = []
    assigned_books = []
    available_books = []
    pending_course_requests = fetchall(
        """
        SELECT
            car.id,
            car.requester_id,
            car.course_id,
            car.note,
            car.created_at,
            u.username,
            u.full_name,
            u.email,
            c.title AS course_title,
            cc.name AS category_name
        FROM course_access_requests car
        JOIN users u ON u.id = car.requester_id
        JOIN courses c ON c.id = car.course_id
        LEFT JOIN course_categories cc ON cc.slug = c.category
        WHERE car.status='pending'
          AND (? IS NULL OR car.requester_id=?)
          AND (? = '' OR c.title LIKE ? OR COALESCE(cc.name, c.category) LIKE ?)
        ORDER BY car.created_at DESC, car.id DESC
        """,
        (selected_user_id, selected_user_id, course_q, f"%{course_q}%", f"%{course_q}%"),
    )

    if selected_user:
        course_like = f"%{course_q}%"
        book_like = f"%{book_q}%"

        assigned_courses = fetchall(
            """
            SELECT
                c.id,
                c.title,
                c.category,
                cc.name AS category_name,
                e.enrolled_at AS granted_at,
                e.granted_by,
                COALESCE(grantor.full_name, grantor.username) AS granted_by_name
            FROM courses c
            JOIN enrollments e ON e.course_id = c.id
            LEFT JOIN course_categories cc ON cc.slug = c.category
            LEFT JOIN users grantor ON grantor.id = e.granted_by
            WHERE e.user_id=?
              AND (? = '' OR c.title LIKE ? OR COALESCE(cc.name, c.category) LIKE ?)
            ORDER BY e.enrolled_at DESC, c.title COLLATE NOCASE
            """,
            (selected_user_id, course_q, course_like, course_like),
        )
        available_courses = fetchall(
            """
            SELECT c.id, c.title, c.category, cc.name AS category_name
            FROM courses c
            LEFT JOIN course_categories cc ON cc.slug = c.category
            WHERE NOT EXISTS (
                SELECT 1 FROM enrollments e WHERE e.user_id=? AND e.course_id=c.id
            )
              AND (? = '' OR c.title LIKE ? OR COALESCE(cc.name, c.category) LIKE ?)
            ORDER BY c.title COLLATE NOCASE
            """,
            (selected_user_id, course_q, course_like, course_like),
        )
        assigned_books = fetchall(
            """
            SELECT
                b.id,
                b.title,
                b.language,
                b.uploaded_by,
                bc.name AS category_name,
                ba.created_at AS granted_at,
                ba.granted_by,
                COALESCE(grantor.full_name, grantor.username) AS granted_by_name
            FROM books b
            JOIN book_access ba ON ba.book_id = b.id
            LEFT JOIN book_categories bc ON bc.id = b.category_id
            LEFT JOIN users grantor ON grantor.id = ba.granted_by
            WHERE ba.user_id=?
              AND (? = '' OR b.title LIKE ? OR COALESCE(bc.name, 'General') LIKE ? OR b.language LIKE ?)
            ORDER BY ba.created_at DESC, b.title COLLATE NOCASE
            """,
            (selected_user_id, book_q, book_like, book_like, book_like),
        )
        available_books = fetchall(
            """
            SELECT b.id, b.title, b.language, b.uploaded_by, bc.name AS category_name
            FROM books b
            LEFT JOIN book_categories bc ON bc.id = b.category_id
            WHERE b.uploaded_by != ?
              AND NOT EXISTS (
                SELECT 1 FROM book_access ba WHERE ba.user_id=? AND ba.book_id=b.id
            )
              AND (? = '' OR b.title LIKE ? OR COALESCE(bc.name, 'General') LIKE ? OR b.language LIKE ?)
            ORDER BY b.title COLLATE NOCASE
            """,
            (selected_user_id, selected_user_id, book_q, book_like, book_like, book_like),
        )

    return render_template(
        "dashboard/admin_access.html",
        users=users_list,
        selected_user=selected_user,
        user_q=user_q,
        course_q=course_q,
        book_q=book_q,
        assigned_courses=assigned_courses,
        available_courses=available_courses,
        assigned_books=assigned_books,
        available_books=available_books,
        pending_course_requests=pending_course_requests,
    )


@admin_bp.route("/users/add", methods=["GET", "POST"])
@admin_like_required
def add_user():
    form_data = request.form if request.method == "POST" else {}

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        scout_unit = request.form.get("scout_unit", "").strip()
        lang = request.form.get("lang", "en")
        role = request.form.get("role", "scout").strip().lower()
        if role not in {"scout", "instructor", "admin"}:
            role = "scout"

        result = auth_service.register_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            scout_unit=scout_unit,
            lang=lang,
        )
        if not result.ok:
            for error in result.errors:
                flash(error, "danger")
            return render_template("dashboard/admin_add_user.html", form_data=form_data)

        execute("UPDATE users SET role=? WHERE id=?", (role, result.user_id))
        flash("User created successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template("dashboard/admin_add_user.html", form_data=form_data)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_like_required
def toggle_user(user_id):
    user = fetchone("SELECT is_active FROM users WHERE id=?", (user_id,))
    if user:
        new_val = 0 if user["is_active"] else 1
        execute("UPDATE users SET is_active=? WHERE id=?", (new_val, user_id))
        return jsonify({"is_active": bool(new_val)})
    return jsonify({"error": "not found"}), 404


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@admin_required
def update_user_role(user_id):
    user = fetchone("SELECT id, username, full_name, role FROM users WHERE id=?", (user_id,))
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    if user["id"] == session["user_id"]:
        flash("You cannot change your own role from the dashboard.", "warning")
        return redirect(url_for("admin.dashboard"))

    if user["role"] == "admin":
        flash("Admin roles cannot be changed from this table.", "warning")
        return redirect(url_for("admin.dashboard"))

    new_role = request.form.get("role", "").strip().lower()
    if new_role not in {"scout", "instructor"}:
        flash("Choose a valid role.", "danger")
        return redirect(url_for("admin.dashboard"))

    if new_role == user["role"]:
        flash("This user already has that role.", "info")
        return redirect(url_for("admin.dashboard"))

    execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
    display_name = user["full_name"] or user["username"]
    flash(f"{display_name} is now {new_role}.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = fetchone("SELECT id, username, full_name, role FROM users WHERE id=?", (user_id,))
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    if user["id"] == session["user_id"]:
        flash("You cannot delete your own account from the dashboard.", "warning")
        return redirect(url_for("admin.dashboard"))

    if user["role"] == "admin":
        flash("Admin accounts cannot be deleted from this table.", "warning")
        return redirect(url_for("admin.dashboard"))

    deleted_media = _cleanup_user_records(user_id, session["user_id"])
    for media_url in deleted_media:
        _delete_local_feed_media(media_url)

    display_name = user["full_name"] or user["username"]
    flash(f"{display_name} was deleted successfully.", "success")
    return redirect(url_for("admin.dashboard"))
