"""routes/dashboard.py — community feed, post interactions, and legacy video detail"""

import re
from collections import defaultdict
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from database import execute, fetchall, fetchone
from kechafa_app.core.security import can_publish_feed_posts, is_admin_like_user
from kechafa_app.services.friend_service import FriendService
from kechafa_app.services.notification_service import NotificationService
from routes.auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)
friend_service = FriendService()
notification_service = NotificationService()

_YT_RE = re.compile(
    r'(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})'
)

def _youtube_embed(url: str) -> str | None:
    m = _YT_RE.search(url)
    return f"https://www.youtube.com/embed/{m.group(1)}?playsinline=1&enablejsapi=1" if m else None

POST_FILTERS = {
    "all": {"label": "All", "icon": "🌐"},
    "text": {"label": "Text", "icon": "📝"},
    "image": {"label": "Photos", "icon": "📸"},
    "video": {"label": "Videos", "icon": "🎥"},
    "reel": {"label": "Reels", "icon": "🎬"},
    "course_announcement": {"label": "Courses", "icon": "📚"},
    "book_announcement": {"label": "Books", "icon": "📘"},
}
VIDEO_POST_TYPES = {"video", "reel"}
MEDIA_POST_TYPES = {"image", "video", "reel"}
CREATABLE_POST_TYPES = {"text", "video", "reel"}
ADMIN_ONLY_POST_TYPES = {"course_announcement", "book_announcement"}
ALLOWED_FEED_VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "m4v"}
ALLOWED_FEED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


class Pagination:
    def __init__(self, items, page, per_page, total):
        self.items = list(items or [])
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = max(1, (total + per_page - 1) // per_page)

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return max(1, self.page - 1)

    @property
    def next_num(self):
        return min(self.pages, self.page + 1)


def _current_user() -> dict | None:
    return fetchone("SELECT * FROM users WHERE id=?", (session["user_id"],))


def _can_create_feed_posts(user: dict | None) -> bool:
    return can_publish_feed_posts(user)


def _can_use_full_feed_features(user: dict | None) -> bool:
    return is_admin_like_user(user)


def _feed_url(feed_filter: str = "all", page: int = 1, post_id: int | None = None) -> str:
    if feed_filter not in POST_FILTERS:
        feed_filter = "all"
    url = url_for("dashboard.feed", filter=feed_filter, page=page)
    if post_id:
        url += f"#post-{post_id}"
    return url


def _feed_redirect(feed_filter: str = "all", page: int = 1, post_id: int | None = None):
    return redirect(_feed_url(feed_filter, page, post_id))


def _composer_redirect(author: dict | None, post_id: int | None = None, anchor: str | None = None):
    target = (request.form.get("return_to") or "feed").strip().lower()
    if target == "profile" and author:
        return redirect(
            url_for(
                "profile.view",
                username=author["username"],
                _anchor=anchor or ("profile-posts" if post_id else "creator-studio"),
            )
        )
    return _feed_redirect(post_id=post_id)


def _save_feed_media(file_storage, folder_name: str, allowed_extensions: set[str], error_message: str) -> str:
    filename = secure_filename(file_storage.filename or "")
    if "." not in filename or filename.rsplit(".", 1)[1].lower() not in allowed_extensions:
        raise ValueError(error_message)

    uploads_dir = Path(current_app.static_folder) / "uploads" / "content" / "feed" / folder_name
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target = uploads_dir / filename

    if target.exists():
        stem = target.stem
        suffix = target.suffix
        counter = 1
        while target.exists():
            target = uploads_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    file_storage.save(target)
    relative_path = target.relative_to(Path(current_app.static_folder)).as_posix()
    return url_for("static", filename=relative_path)


def _save_feed_video(file_storage) -> str:
    return _save_feed_media(
        file_storage,
        "video",
        ALLOWED_FEED_VIDEO_EXTENSIONS,
        "Please upload a valid video file (.mp4, .mov, .webm, .m4v).",
    )


def _save_feed_image(file_storage) -> str:
    return _save_feed_media(
        file_storage,
        "image",
        ALLOWED_FEED_IMAGE_EXTENSIONS,
        "Please upload a valid image file (.png, .jpg, .jpeg, .webp, .gif).",
    )


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


def _post_exists(post_id: int) -> bool:
    return bool(fetchone("SELECT id FROM feed_posts WHERE id=? AND is_published=1", (post_id,)))


def _get_post_summary(post_id: int) -> dict | None:
    return fetchone(
        """
        SELECT fp.id, fp.title, fp.author_id, fp.post_type
        FROM feed_posts fp
        WHERE fp.id=? AND fp.is_published=1
        """,
        (post_id,),
    )


def _format_duration(secs):
    if not secs:
        return "—"
    minutes, seconds = divmod(int(secs), 60)
    return f"{minutes}:{seconds:02d}"


@dashboard_bp.route("/feed")
@login_required
def feed():
    uid = session["user_id"]
    active_filter = request.args.get("filter", "all")
    if active_filter not in POST_FILTERS:
        active_filter = "all"

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 8
    offset = (page - 1) * per_page
    current_user = _current_user()
    can_create_posts = _can_create_feed_posts(current_user)
    can_use_full_feed_features = _can_use_full_feed_features(current_user)

    post_where = "WHERE fp.is_published=1 AND fp.post_type NOT IN ('image')"
    post_params: list = []
    if active_filter == "reel":
        post_where += " AND fp.post_type='reel'"
    elif active_filter != "all":
        post_where += " AND fp.post_type=?"
        post_params.append(active_filter)

    total = (fetchone(f"SELECT COUNT(*) as c FROM feed_posts fp {post_where}", tuple(post_params)) or {}).get("c", 0)

    post_rows = fetchall(
        f"""
        SELECT
            fp.*,
            u.username AS author_username,
            u.full_name AS author_full_name,
            u.avatar_url AS author_avatar,
            u.role AS author_role,
            u.level_rank AS author_level_rank,
            c.title AS linked_course_title,
            c.thumbnail_url AS linked_course_thumbnail,
            c.category AS linked_course_category,
            b.title AS linked_book_title,
            b.language AS linked_book_language,
            bc.name AS linked_book_category,
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
            ) AS share_count,
            EXISTS(
                SELECT 1 FROM post_likes pl2
                WHERE pl2.post_id = fp.id AND pl2.user_id = ?
            ) AS liked
        FROM feed_posts fp
        JOIN users u ON u.id = fp.author_id
        LEFT JOIN courses c ON c.id = fp.course_id
        LEFT JOIN books b ON b.id = fp.book_id
        LEFT JOIN book_categories bc ON bc.id = b.category_id
        {post_where}
        ORDER BY fp.is_pinned DESC, fp.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (uid, *post_params, per_page, offset),
    )
    posts = Pagination(post_rows, page, per_page, total)

    comments_by_post: dict[int, list[dict]] = defaultdict(list)
    post_ids = [post["id"] for post in posts.items]
    if post_ids:
        placeholders = ",".join("?" for _ in post_ids)
        comments = fetchall(
            f"""
            SELECT
                pc.*,
                u.username,
                u.full_name,
                u.avatar_url AS author_avatar
            FROM post_comments pc
            JOIN users u ON u.id = pc.author_id
            WHERE pc.post_id IN ({placeholders})
            ORDER BY pc.created_at ASC
            """,
            tuple(post_ids),
        )
        for comment in comments:
            comments_by_post[comment["post_id"]].append(comment)

    for post in posts.items:
        post["comments"] = comments_by_post.get(post["id"], [])
        post["liked"] = bool(post.get("liked"))
        post["duration_display"] = _format_duration(post.get("duration_secs"))

    my_groups = fetchall(
        "SELECT cg.*, "
        "(SELECT COUNT(*) FROM group_members gm2 WHERE gm2.group_id=cg.id) AS member_count "
        "FROM community_groups cg "
        "JOIN group_members gm ON cg.id=gm.group_id WHERE gm.user_id=? LIMIT 3",
        (uid,),
    )
    notifications = notification_service.list_for_user(uid, unread_only=True, limit=5)
    badge_count = (fetchone("SELECT COUNT(*) as c FROM user_badges WHERE user_id=?", (uid,)) or {}).get("c", 0)
    friend_suggestions = fetchall(
        """
        SELECT
            u.id,
            u.username,
            u.full_name,
            u.avatar_url,
            u.role,
            u.scout_unit,
            COALESCE((
                SELECT fr.status
                FROM friend_requests fr
                WHERE (
                    (fr.sender_id = ? AND fr.receiver_id = u.id)
                    OR (fr.sender_id = u.id AND fr.receiver_id = ?)
                )
                ORDER BY fr.id DESC
                LIMIT 1
            ), 'none') AS friend_status,
            EXISTS(
                SELECT 1 FROM friend_requests fr
                WHERE fr.sender_id = u.id AND fr.receiver_id = ? AND fr.status = 'pending'
            ) AS incoming_request
        FROM users u
        WHERE u.id != ?
        ORDER BY u.last_seen DESC, u.created_at DESC
        LIMIT 6
        """,
        (uid, uid, uid, uid),
    )
    creator_courses = []
    creator_books = []
    reel_strip = fetchall(
        """
        SELECT
            fp.id,
            fp.title,
            fp.body,
            fp.media_url,
            fp.created_at,
            u.username AS author_username,
            u.full_name AS author_full_name,
            u.avatar_url AS author_avatar
        FROM feed_posts fp
        JOIN users u ON u.id = fp.author_id
        WHERE fp.is_published=1 AND fp.post_type='reel'
        ORDER BY fp.is_pinned DESC, fp.created_at DESC
        LIMIT 8
        """
    )
    if is_admin_like_user(current_user):
        creator_courses = fetchall(
            "SELECT id, title FROM courses WHERE is_published=1 ORDER BY title COLLATE NOCASE"
        )
        creator_books = fetchall(
            "SELECT b.id, b.title, COALESCE(bc.name, 'General') AS category_name "
            "FROM books b "
            "LEFT JOIN book_categories bc ON bc.id = b.category_id "
            "ORDER BY b.title COLLATE NOCASE"
        )
    return render_template(
        "dashboard/feed.html",
        posts=posts,
        active_filter=active_filter,
        post_filters=POST_FILTERS,
        current_feed_user=current_user,
        can_create_posts=can_create_posts,
        can_use_full_feed_features=can_use_full_feed_features,
        reel_strip=reel_strip,
        creator_courses=creator_courses,
        creator_books=creator_books,
        friend_suggestions=friend_suggestions,
        my_groups=my_groups,
        notifications=notifications,
        badge_count=badge_count,
    )


@dashboard_bp.route("/feed/posts/create", methods=["POST"])
@login_required
def create_feed_post():
    post_type = request.form.get("post_type", "text").strip()
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    media_url = request.form.get("media_url", "").strip()
    category = request.form.get("category", "general").strip() or "general"
    media_file = request.files.get("media_file")
    course_id = request.form.get("course_id", type=int)
    book_id = request.form.get("book_id", type=int)
    author = _current_user()
    is_pinned = 1 if is_admin_like_user(author) and request.form.get("is_pinned") else 0
    linked_course = None
    linked_book = None

    if not _can_create_feed_posts(author):
        flash("Only admins and instructors can publish feed posts.", "danger")
        return _composer_redirect(author)

    allowed_post_types: set[str] = set()
    if _can_create_feed_posts(author):
        allowed_post_types.update(CREATABLE_POST_TYPES)
    if _can_use_full_feed_features(author):
        allowed_post_types.update(ADMIN_ONLY_POST_TYPES)

    if post_type not in allowed_post_types:
        flash("Choose a valid post type.", "danger")
        return _composer_redirect(author)

    if post_type == "text":
        if not body and not title:
            flash("Add a title or message for the text post.", "danger")
            return _composer_redirect(author)
        if not title:
            title = body[:70] + ("..." if len(body) > 70 else "")
        category = "community"

    elif post_type in VIDEO_POST_TYPES:
        if not title:
            flash("Add a title for the video post.", "danger")
            return _composer_redirect(author)
        if media_file and media_file.filename:
            try:
                media_url = _save_feed_video(media_file)
            except ValueError as exc:
                flash(str(exc), "danger")
                return _composer_redirect(author)
        if not media_url:
            flash("Add a video URL or upload a video file.", "danger")
            return _composer_redirect(author)
        if media_url and not media_url.startswith(("http://", "https://", "/")):
            flash("The video URL must start with http:// or https://", "danger")
            return _composer_redirect(author)
        yt = _youtube_embed(media_url)
        if yt:
            media_url = yt

    elif post_type == "course_announcement":
        linked_course = fetchone(
            "SELECT id, title, description, category FROM courses WHERE id=? AND is_published=1",
            (course_id,),
        )
        if not linked_course:
            flash("Choose a valid course for the announcement.", "danger")
            return _composer_redirect(author)
        if not title:
            title = f"Course Update: {linked_course['title']}"
        if not body:
            body = linked_course.get("description") or "A course update is now available."
        category = linked_course.get("category") or "general"

    elif post_type == "book_announcement":
        linked_book = fetchone(
            "SELECT id, title, description FROM books WHERE id=?",
            (book_id,),
        )
        if not linked_book:
            flash("Choose a valid book for the announcement.", "danger")
            return _composer_redirect(author)
        if not title:
            title = f"Library Update: {linked_book['title']}"
        if not body:
            body = linked_book.get("description") or "A new library book is available."
        category = "library"

    post_id = execute(
        """
        INSERT INTO feed_posts (
            author_id, post_type, title, body, media_url, category, course_id, book_id, is_pinned
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            post_type,
            title,
            body or None,
            media_url or None,
            category or None,
            linked_course["id"] if linked_course else None,
            linked_book["id"] if linked_book else None,
            is_pinned,
        ),
    )
    notification_service.notify_post_published(
        user_id=session["user_id"],
        post_id=post_id,
        title=title,
        post_type=post_type,
    )
    flash("Post published to the feed.", "success")
    return _composer_redirect(author, post_id=post_id)


@dashboard_bp.route("/feed/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_feed_post(post_id):
    author = _current_user()
    post = fetchone("SELECT id, title, media_url, author_id FROM feed_posts WHERE id=?", (post_id,))
    if not post:
        flash("Post not found.", "danger")
        return _feed_redirect()

    is_own_post = post["author_id"] == author["id"]
    if not is_own_post and not _can_use_full_feed_features(author):
        flash("You don't have permission to delete this post.", "danger")
        return _feed_redirect()

    execute("DELETE FROM post_likes WHERE post_id=?", (post_id,))
    execute("DELETE FROM post_comments WHERE post_id=?", (post_id,))
    execute("DELETE FROM post_shares WHERE post_id=?", (post_id,))
    execute("DELETE FROM feed_posts WHERE id=?", (post_id,))
    _delete_local_feed_media(post.get("media_url"))

    flash(f"Post '{post.get('title') or 'Untitled post'}' deleted.", "success")
    return_to = request.form.get("return_to")
    if return_to == "profile":
        username = fetchone("SELECT username FROM users WHERE id=?", (author["id"],))
        if username:
            return redirect(url_for("profile.view", username=username["username"]))
    return _feed_redirect()


@dashboard_bp.route("/feed/posts/<int:post_id>/like", methods=["POST"])
@login_required
def toggle_post_like(post_id):
    if not _post_exists(post_id):
        return jsonify({"error": "Post not found."}), 404

    uid = session["user_id"]
    existing = fetchone("SELECT id FROM post_likes WHERE user_id=? AND post_id=?", (uid, post_id))
    if existing:
        execute("DELETE FROM post_likes WHERE user_id=? AND post_id=?", (uid, post_id))
        liked = False
    else:
        execute("INSERT INTO post_likes (user_id, post_id) VALUES (?, ?)", (uid, post_id))
        liked = True
        post = _get_post_summary(post_id)
        actor = _current_user()
        if post and actor:
            notification_service.notify_post_liked(
                recipient_id=post["author_id"],
                actor=actor,
                post_id=post_id,
                post_title=post.get("title") or "Untitled post",
            )

    count = (fetchone("SELECT COUNT(*) as c FROM post_likes WHERE post_id=?", (post_id,)) or {}).get("c", 0)
    return jsonify({"liked": liked, "count": count})


@dashboard_bp.route("/feed/posts/<int:post_id>/share", methods=["POST"])
@login_required
def share_post(post_id):
    if not _post_exists(post_id):
        return jsonify({"error": "Post not found."}), 404

    execute("INSERT INTO post_shares (post_id, user_id) VALUES (?, ?)", (post_id, session["user_id"]))
    count = (fetchone("SELECT COUNT(*) as c FROM post_shares WHERE post_id=?", (post_id,)) or {}).get("c", 0)
    return jsonify({"count": count, "share_url": _feed_url(post_id=post_id)})


@dashboard_bp.route("/feed/posts/<int:post_id>/comment", methods=["POST"])
@login_required
def add_post_comment(post_id):
    feed_filter = request.form.get("feed_filter", "all")
    page = max(1, request.form.get("page", 1, type=int))
    body = request.form.get("body", "").strip()

    if not _post_exists(post_id):
        flash("Post not found.", "danger")
        return _feed_redirect(feed_filter, page)

    if not body:
        flash("Write a comment before posting.", "warning")
        return _feed_redirect(feed_filter, page, post_id)

    execute(
        "INSERT INTO post_comments (post_id, author_id, body) VALUES (?, ?, ?)",
        (post_id, session["user_id"], body),
    )
    post = _get_post_summary(post_id)
    actor = _current_user()
    if post and actor:
        notification_service.notify_post_commented(
            recipient_id=post["author_id"],
            actor=actor,
            post_id=post_id,
            comment_body=body,
        )
    flash("Comment added.", "success")
    return _feed_redirect(feed_filter, page, post_id)


@dashboard_bp.route(
    "/feed/posts/<int:post_id>/comment/<int:comment_id>/delete",
    methods=["POST"],
)
@login_required
def delete_post_comment(post_id: int, comment_id: int):
    feed_filter = request.form.get("feed_filter", "all")
    page = max(1, request.form.get("page", 1, type=int))

    if not _post_exists(post_id):
        flash("Post not found.", "danger")
        return _feed_redirect(feed_filter, page)

    comment = fetchone(
        "SELECT id, post_id, author_id FROM post_comments WHERE id=? AND post_id=?",
        (comment_id, post_id),
    )
    if not comment:
        flash("Comment not found.", "danger")
        return _feed_redirect(feed_filter, page, post_id)

    user = _current_user()
    if not user:
        flash("Please sign in to continue.", "danger")
        return redirect(url_for("auth.login"))

    if comment["author_id"] != user["id"] and not is_admin_like_user(user):
        flash("Insufficient permissions.", "danger")
        return _feed_redirect(feed_filter, page, post_id)

    execute("DELETE FROM post_comments WHERE id=?", (comment_id,))
    flash("Comment removed.", "success")
    return _feed_redirect(feed_filter, page, post_id)


@dashboard_bp.route(
    "/feed/posts/<int:post_id>/comment/<int:comment_id>/update",
    methods=["POST"],
)
@login_required
def update_post_comment(post_id: int, comment_id: int):
    feed_filter = request.form.get("feed_filter", "all")
    page = max(1, request.form.get("page", 1, type=int))
    body = request.form.get("body", "").strip()

    if not _post_exists(post_id):
        flash("Post not found.", "danger")
        return _feed_redirect(feed_filter, page)

    comment = fetchone(
        "SELECT id, post_id, author_id FROM post_comments WHERE id=? AND post_id=?",
        (comment_id, post_id),
    )
    if not comment:
        flash("Comment not found.", "danger")
        return _feed_redirect(feed_filter, page, post_id)

    user = _current_user()
    if not user:
        flash("Please sign in to continue.", "danger")
        return redirect(url_for("auth.login"))

    if comment["author_id"] != user["id"] and not is_admin_like_user(user):
        flash("Insufficient permissions.", "danger")
        return _feed_redirect(feed_filter, page, post_id)

    if not body:
        flash("Write a comment before saving.", "warning")
        return _feed_redirect(feed_filter, page, post_id)

    execute("UPDATE post_comments SET body=? WHERE id=?", (body, comment_id))
    flash("Comment updated.", "success")
    return _feed_redirect(feed_filter, page, post_id)


@dashboard_bp.route("/feed/friends/request/<int:user_id>", methods=["POST"])
@login_required
def send_friend_request(user_id):
    result = friend_service.send_or_accept_request(session["user_id"], user_id)
    if not result.ok:
        return jsonify({"error": result.error}), result.status_code
    return jsonify({"status": result.status, "label": result.label, "message": result.message})

    sender_id = session["user_id"]
    if user_id == sender_id:
        return jsonify({"error": "You cannot add yourself."}), 400

    receiver = fetchone("SELECT id, full_name, username FROM users WHERE id=?", (user_id,))
    if not receiver:
        return jsonify({"error": "User not found."}), 404

    sender = _current_user() or {}
    sender_name = sender.get("full_name") or sender.get("username") or "A user"

    existing = fetchone(
        """
        SELECT *
        FROM friend_requests
        WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
        ORDER BY id DESC
        LIMIT 1
        """,
        (sender_id, user_id, user_id, sender_id),
    )

    if existing and existing.get("status") == "accepted":
        return jsonify({"status": "accepted", "label": "Friends", "message": "You are already friends."})
    elif existing and existing.get("status") == "pending":
        if existing.get("sender_id") == sender_id:
            return jsonify({"status": "pending", "label": "Pending", "message": "Friend request already sent."})
        else:
            execute(
                "UPDATE friend_requests SET status='accepted', responded_at=datetime('now') WHERE id=?",
                (existing["id"],),
            )
            execute(
                "INSERT INTO notifications (user_id,kind,title,body,icon) VALUES (?,?,?,?,?)",
                (
                    user_id,
                    "friend_accept",
                    "Friend request accepted",
                    f"{sender_name} accepted your request.",
                    "🤝",
                ),
            )
            return jsonify({"status": "accepted", "label": "Friends", "message": "Friend request accepted."})
    else:
        execute(
            "INSERT INTO friend_requests (sender_id, receiver_id, status) VALUES (?, ?, 'pending')",
            (sender_id, user_id),
        )
        execute(
            "INSERT INTO notifications (user_id,kind,title,body,icon) VALUES (?,?,?,?,?)",
            (
                user_id,
                "friend_request",
                "New friend request",
                f"{sender_name} wants to connect with you.",
                "🤝",
            ),
        )
        return jsonify({"status": "pending", "label": "Pending", "message": "Friend request sent."})


@dashboard_bp.route("/video/<int:video_id>")
@login_required
def video_detail(video_id):
    uid = session["user_id"]
    video = fetchone(
        "SELECT v.*, u.username, u.full_name, u.avatar_url as uavatar, u.level_rank, u.role as urole, c.title as course_title "
        "FROM videos v "
        "JOIN users u ON v.uploader_id=u.id "
        "LEFT JOIN courses c ON c.id=v.course_id "
        "WHERE v.id=?",
        (video_id,),
    )
    if not video:
        flash("Video not found.", "danger")
        return redirect(url_for("dashboard.feed"))

    comments = fetchall(
        "SELECT c.*, u.username, u.full_name, u.avatar_url as uavatar "
        "FROM comments c JOIN users u ON c.author_id=u.id "
        "WHERE c.video_id=? ORDER BY c.created_at ASC",
        (video_id,),
    )
    liked = bool(fetchone("SELECT 1 FROM likes WHERE user_id=? AND video_id=?", (uid, video_id)))
    like_count = (fetchone("SELECT COUNT(*) as c FROM likes WHERE video_id=?", (video_id,)) or {}).get("c", 0)
    video["like_count"] = like_count

    session_key = f"viewed_{video_id}"
    if not session.get(session_key):
        execute("UPDATE videos SET view_count=view_count+1 WHERE id=?", (video_id,))
        xp = video.get("xp_reward", 50)
        execute(
            "UPDATE users SET level_points=level_points+?, total_reels_watched=total_reels_watched+1 WHERE id=?",
            (xp, uid),
        )
        execute("UPDATE users SET level_rank=MAX(1,level_points/1000) WHERE id=?", (uid,))
        execute(
            "INSERT INTO notifications (user_id,kind,title,body,icon) VALUES (?,?,?,?,?)",
            (uid, "xp_award", f"+{xp} XP earned! ⚡", f"You watched '{video['title']}'", "⚡"),
        )
        session[session_key] = True

    related = fetchall(
        "SELECT v.*, (SELECT COUNT(*) FROM likes WHERE video_id=v.id) as like_count "
        "FROM videos v WHERE v.category=? AND v.id!=? AND v.is_published=1 LIMIT 4",
        (video.get("category"), video_id),
    )

    video["duration_display"] = _format_duration(video.get("duration_secs"))
    for row in related:
        row["duration_display"] = _format_duration(row.get("duration_secs"))

    return render_template(
        "dashboard/video_detail.html",
        video=video,
        comments=comments,
        liked=liked,
        like_count=like_count,
        related=related,
    )


@dashboard_bp.route("/video/<int:video_id>/like", methods=["POST"])
@login_required
def toggle_like(video_id):
    uid = session["user_id"]
    existing = fetchone("SELECT id FROM likes WHERE user_id=? AND video_id=?", (uid, video_id))
    if existing:
        execute("DELETE FROM likes WHERE user_id=? AND video_id=?", (uid, video_id))
        liked = False
    else:
        execute("INSERT INTO likes (user_id,video_id) VALUES (?,?)", (uid, video_id))
        liked = True
    count = (fetchone("SELECT COUNT(*) as c FROM likes WHERE video_id=?", (video_id,)) or {}).get("c", 0)
    return jsonify({"liked": liked, "count": count})


@dashboard_bp.route("/video/<int:video_id>/comment", methods=["POST"])
@login_required
def add_comment(video_id):
    body = request.form.get("body", "").strip()
    if body:
        execute(
            "INSERT INTO comments (body,author_id,video_id) VALUES (?,?,?)",
            (body, session["user_id"], video_id),
        )
    return redirect(url_for("dashboard.video_detail", video_id=video_id))
