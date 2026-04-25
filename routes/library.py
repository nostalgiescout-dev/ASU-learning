import os
import re
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from database import execute, fetchall, fetchone
from i18n import t
from kechafa_app.services.notification_service import NotificationService
from routes.auth import admin_like_required, login_required

library_bp = Blueprint("library", __name__, url_prefix="/library")
notification_service = NotificationService()

UPLOAD_FOLDER = os.path.join("static", "uploads", "books")
COVER_UPLOAD_FOLDER = os.path.join("static", "uploads", "book-covers")
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx"}
ALLOWED_COVER_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_FILE_LABEL = "PDF, Word, or PowerPoint files"
ALLOWED_COVER_LABEL = "PNG, JPG, JPEG, or WEBP images"

Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
Path(COVER_UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_cover_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_COVER_EXTENSIONS


def _book_disk_path(file_path: str) -> str:
    relative_path = file_path.lstrip("/").replace("/", os.sep)
    return os.path.join(current_app.static_folder, relative_path)


def _delete_file_if_exists(file_path: str | None) -> None:
    if not file_path:
        return

    disk_path = _book_disk_path(file_path)
    try:
        if os.path.exists(disk_path):
            os.remove(disk_path)
    except OSError:
        pass


def _detach_book_dependencies(book_id: int) -> None:
    execute("UPDATE feed_posts SET book_id=NULL WHERE book_id=?", (book_id,))
    execute("DELETE FROM book_access WHERE book_id=?", (book_id,))


def _current_user_role() -> str | None:
    return (fetchone("SELECT role FROM users WHERE id=?", (session["user_id"],)) or {}).get("role")


def _book_access_filter(user_id: int, role: str | None) -> tuple[str, tuple]:
    return "1=1", ()


def _user_can_access_book(book: dict | None, user_id: int, role: str | None) -> bool:
    return book is not None


def _fetch_categories(with_counts: bool = False, user_id: int | None = None, role: str | None = None) -> list[dict]:
    if with_counts:
        return fetchall(
            """
            SELECT
                c.*,
                COUNT(b.id) AS book_count
            FROM book_categories c
            LEFT JOIN books b ON b.category_id = c.id
            GROUP BY c.id
            ORDER BY CASE WHEN c.slug='general' THEN 0 ELSE 1 END, c.name COLLATE NOCASE
            """
        )

    return fetchall(
        """
        SELECT *
        FROM book_categories
        ORDER BY CASE WHEN slug='general' THEN 0 ELSE 1 END, name COLLATE NOCASE
        """
    )


def _get_category(category_id: int) -> dict | None:
    return fetchone("SELECT * FROM book_categories WHERE id=?", (category_id,))


def _get_fallback_category(excluded_id: int) -> dict | None:
    fallback = fetchone(
        """
        SELECT *
        FROM book_categories
        WHERE id<>?
        ORDER BY CASE WHEN slug='general' THEN 0 ELSE 1 END, name COLLATE NOCASE
        LIMIT 1
        """,
        (excluded_id,),
    )
    return fallback


def _get_book(book_id: int) -> dict | None:
    return fetchone(
        """
        SELECT
            b.*,
            c.name AS category_name,
            c.slug AS category_slug,
            u.full_name AS uploader_name
        FROM books b
        LEFT JOIN book_categories c ON c.id = b.category_id
        JOIN users u ON u.id = b.uploaded_by
        WHERE b.id=?
        """,
        (book_id,),
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "category"


def _build_unique_category_slug(name: str, current_id: int | None = None) -> str:
    base_slug = _slugify(name)
    slug = base_slug
    suffix = 2

    while True:
        existing = fetchone("SELECT id FROM book_categories WHERE slug=?", (slug,))
        if not existing or existing["id"] == current_id:
            return slug
        slug = f"{base_slug}-{suffix}"
        suffix += 1


def _save_uploaded_document(file_storage) -> tuple[str, str]:
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ValueError("No file selected")
    if not allowed_file(filename):
        raise ValueError(f"Only {ALLOWED_FILE_LABEL} are allowed")

    stem, ext = os.path.splitext(filename)
    unique_name = f"{secure_filename(stem)}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext.lower()}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file_storage.save(save_path)
    return unique_name, os.path.join("uploads", "books", unique_name).replace("\\", "/")


def _save_uploaded_cover(file_storage) -> tuple[str, str]:
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ValueError("No cover image selected")
    if not allowed_cover_file(filename):
        raise ValueError(f"Only {ALLOWED_COVER_LABEL} are allowed for book covers")

    stem, ext = os.path.splitext(filename)
    unique_name = f"{secure_filename(stem)}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext.lower()}"
    save_path = os.path.join(COVER_UPLOAD_FOLDER, unique_name)
    file_storage.save(save_path)
    return unique_name, os.path.join("uploads", "book-covers", unique_name).replace("\\", "/")


def _group_books_by_category(books: list[dict], categories: list[dict]) -> list[dict]:
    grouped = []
    books_by_category = {category["id"]: [] for category in categories}
    for book in books:
        books_by_category.setdefault(book["category_id"], []).append(book)

    for category in categories:
        category_copy = dict(category)
        category_copy["books"] = books_by_category.get(category["id"], [])
        grouped.append(category_copy)

    return grouped


@library_bp.route("/")
@login_required
def index():
    user_id = session["user_id"]
    role = _current_user_role()
    selected_category_id = request.args.get("category", type=int)
    categories = _fetch_categories(with_counts=True, user_id=user_id, role=role)
    access_filter, access_params = _book_access_filter(user_id, role)
    filters = [access_filter]
    params: list[int] = list(access_params)
    if selected_category_id:
        filters.append("b.category_id=?")
        params.append(selected_category_id)

    books = fetchall(
        """
        SELECT
            b.*,
            c.name AS category_name,
            c.slug AS category_slug,
            u.full_name AS uploader_name
        FROM books b
        LEFT JOIN book_categories c ON c.id = b.category_id
        JOIN users u ON u.id = b.uploaded_by
        WHERE """ + " AND ".join(filters) + """
        ORDER BY c.name COLLATE NOCASE, b.created_at DESC, b.title COLLATE NOCASE
        """,
        tuple(params),
    )

    selected_category = None
    if selected_category_id:
        selected_category = next((category for category in categories if category["id"] == selected_category_id), None)

    category_sections = _group_books_by_category(books, categories)
    has_books = any(category["books"] for category in category_sections)

    return render_template(
        "library/index.html",
        categories=categories,
        category_sections=category_sections,
        has_books=has_books,
        selected_category=selected_category,
    )


@library_bp.route("/categories", methods=["GET", "POST"])
@admin_like_required
def manage_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        lang = session.get("lang", "en")

        if not name:
            flash(t("Please provide category name", lang), "danger")
            return redirect(url_for("library.manage_categories"))

        existing = fetchone("SELECT id FROM book_categories WHERE lower(name)=lower(?)", (name,))
        if existing:
            flash(t("Category already exists", lang), "danger")
            return redirect(url_for("library.manage_categories"))

        execute(
            "INSERT INTO book_categories (name, slug, description, created_by) VALUES (?, ?, ?, ?)",
            (name, _build_unique_category_slug(name), description, session["user_id"]),
        )
        flash(t("Category added successfully", lang), "success")
        return redirect(url_for("library.manage_categories"))

    categories = _fetch_categories(with_counts=True)
    return render_template("library/categories.html", categories=categories)


@library_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_like_required
def edit_category(category_id: int):
    category = _get_category(category_id)
    if not category:
        flash(t("Category not found", session.get("lang", "en")), "danger")
        return redirect(url_for("library.manage_categories"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        lang = session.get("lang", "en")

        if not name:
            flash(t("Please provide category name", lang), "danger")
            return redirect(url_for("library.edit_category", category_id=category_id))

        existing = fetchone(
            "SELECT id FROM book_categories WHERE lower(name)=lower(?) AND id<>?",
            (name, category_id),
        )
        if existing:
            flash(t("Category already exists", lang), "danger")
            return redirect(url_for("library.edit_category", category_id=category_id))

        execute(
            "UPDATE book_categories SET name=?, slug=?, description=? WHERE id=?",
            (name, _build_unique_category_slug(name, current_id=category_id), description, category_id),
        )
        flash(t("Category updated successfully", lang), "success")
        return redirect(url_for("library.manage_categories"))

    return render_template("library/category_form.html", category=category, is_edit=True)


@library_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_like_required
def delete_category(category_id: int):
    category = _get_category(category_id)
    lang = session.get("lang", "en")
    if not category:
        flash(t("Category not found", lang), "danger")
        return redirect(url_for("library.manage_categories"))

    books_count = fetchone("SELECT COUNT(*) AS c FROM books WHERE category_id=?", (category_id,))
    if books_count and books_count["c"] > 0:
        fallback = _get_fallback_category(category_id)
        if not fallback:
            flash(t("At least one category is required", lang), "danger")
            return redirect(url_for("library.manage_categories"))

        execute(
            "UPDATE books SET category_id=? WHERE category_id=?",
            (fallback["id"], category_id),
        )
        execute("DELETE FROM book_categories WHERE id=?", (category_id,))
        flash(
            t(
                f"Category deleted successfully. Books were moved to {fallback['name']}.",
                lang,
            ),
            "success",
        )
        return redirect(url_for("library.manage_categories"))

    categories_count = fetchone("SELECT COUNT(*) AS c FROM book_categories")
    if categories_count and categories_count["c"] <= 1:
        flash(t("At least one category is required", lang), "danger")
        return redirect(url_for("library.manage_categories"))

    execute("DELETE FROM book_categories WHERE id=?", (category_id,))
    flash(t("Category deleted successfully", lang), "success")
    return redirect(url_for("library.manage_categories"))


@library_bp.route("/add", methods=["GET", "POST"])
@admin_like_required
def add_book():
    categories = _fetch_categories()
    lang = session.get("lang", "en")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        language = request.form.get("language", "en")
        category_id = request.form.get("category_id", type=int)
        file = request.files.get("file")
        cover_image = request.files.get("cover_image")
        form_data = request.form.to_dict()

        if not title:
            flash(t("Please provide title", lang), "danger")
            return render_template("library/add.html", is_edit=False, book=None, categories=categories, form_data=form_data)

        category = _get_category(category_id) if category_id else None
        if not category:
            flash(t("Please select a category", lang), "danger")
            return render_template("library/add.html", is_edit=False, book=None, categories=categories, form_data=form_data)

        if not file or not file.filename:
            flash(t("No file selected", lang), "danger")
            return render_template("library/add.html", is_edit=False, book=None, categories=categories, form_data=form_data)

        try:
            _, file_path = _save_uploaded_document(file)
        except ValueError as exc:
            flash(t(str(exc), lang), "danger")
            return render_template("library/add.html", is_edit=False, book=None, categories=categories, form_data=form_data)

        cover_image_path = None
        if cover_image and cover_image.filename:
            try:
                _, cover_image_path = _save_uploaded_cover(cover_image)
            except ValueError as exc:
                _delete_file_if_exists(file_path)
                flash(t(str(exc), lang), "danger")
                return render_template("library/add.html", is_edit=False, book=None, categories=categories, form_data=form_data)

        book_id = execute(
            """
            INSERT INTO books (title, description, file_path, cover_image_path, language, category_id, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, file_path, cover_image_path, language, category_id, session["user_id"]),
        )
        notification_service.notify_book_published(
            uploader_id=session["user_id"],
            book_id=book_id,
            title=title,
        )
        flash(t("Book added successfully", lang), "success")
        return redirect(url_for("library.index", category=category_id))

    return render_template("library/add.html", is_edit=False, book=None, categories=categories, form_data={})


@library_bp.route("/edit/<int:book_id>", methods=["GET", "POST"])
@admin_like_required
def edit_book(book_id: int):
    book = _get_book(book_id)
    if not book:
        flash(t("Book not found", session.get("lang", "en")), "danger")
        return redirect(url_for("library.index"))

    categories = _fetch_categories()
    lang = session.get("lang", "en")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        language = request.form.get("language", "en")
        category_id = request.form.get("category_id", type=int)
        file = request.files.get("file")
        cover_image = request.files.get("cover_image")
        form_data = request.form.to_dict()

        if not title:
            flash(t("Please provide title", lang), "danger")
            return render_template("library/add.html", is_edit=True, book=book, categories=categories, form_data=form_data)

        category = _get_category(category_id) if category_id else None
        if not category:
            flash(t("Please select a category", lang), "danger")
            return render_template("library/add.html", is_edit=True, book=book, categories=categories, form_data=form_data)

        file_path = book["file_path"]
        current_cover_image_path = book.get("cover_image_path")
        cover_image_path = current_cover_image_path
        if file and file.filename:
            try:
                _, file_path = _save_uploaded_document(file)
            except ValueError as exc:
                flash(t(str(exc), lang), "danger")
                return render_template("library/add.html", is_edit=True, book=book, categories=categories, form_data=form_data)
        if cover_image and cover_image.filename:
            try:
                _, cover_image_path = _save_uploaded_cover(cover_image)
            except ValueError as exc:
                if file_path != book["file_path"]:
                    _delete_file_if_exists(file_path)
                flash(t(str(exc), lang), "danger")
                return render_template("library/add.html", is_edit=True, book=book, categories=categories, form_data=form_data)

        if file_path != book["file_path"]:
            _delete_file_if_exists(book["file_path"])
        if cover_image_path != current_cover_image_path:
            _delete_file_if_exists(current_cover_image_path)

        execute(
            """
            UPDATE books
            SET title=?, description=?, file_path=?, cover_image_path=?, language=?, category_id=?
            WHERE id=?
            """,
            (title, description, file_path, cover_image_path, language, category_id, book_id),
        )
        flash(t("Book updated successfully", lang), "success")
        return redirect(url_for("library.index", category=category_id))

    form_data = {
        "title": book["title"],
        "description": book.get("description") or "",
        "language": book["language"],
        "category_id": book.get("category_id"),
    }
    return render_template("library/add.html", is_edit=True, book=book, categories=categories, form_data=form_data)


@library_bp.route("/delete/<int:book_id>", methods=["POST"])
@admin_like_required
def delete_book(book_id: int):
    book = _get_book(book_id)
    lang = session.get("lang", "en")
    if not book:
        flash(t("Book not found", lang), "danger")
        return redirect(url_for("library.index"))

    _detach_book_dependencies(book_id)
    _delete_file_if_exists(book["file_path"])
    _delete_file_if_exists(book.get("cover_image_path"))
    execute("DELETE FROM books WHERE id=?", (book_id,))
    flash(t("Book deleted successfully", lang), "success")
    return redirect(url_for("library.index"))


@library_bp.route("/view/<int:book_id>")
@login_required
def view_book(book_id: int):
    user_id = session["user_id"]
    role = _current_user_role()
    book = _get_book(book_id)
    if not book:
        abort(404)
    if not _user_can_access_book(book, user_id, role):
        abort(403)
    notification_service.mark_related_as_read(user_id, entity_type="book", entity_id=book_id)

    abs_file_path = _book_disk_path(book["file_path"])
    if not os.path.isfile(abs_file_path):
        abort(404)

    directory = os.path.dirname(abs_file_path)
    filename = os.path.basename(abs_file_path)
    return send_from_directory(directory, filename, as_attachment=False)


@library_bp.route("/download/<int:book_id>")
@login_required
def download_book(book_id: int):
    user_id = session["user_id"]
    role = _current_user_role()
    book = _get_book(book_id)
    if not book:
        abort(404)
    if not _user_can_access_book(book, user_id, role):
        abort(403)
    notification_service.mark_related_as_read(user_id, entity_type="book", entity_id=book_id)

    abs_file_path = _book_disk_path(book["file_path"])
    if not os.path.isfile(abs_file_path):
        abort(404)

    directory = os.path.dirname(abs_file_path)
    filename = os.path.basename(abs_file_path)
    return send_from_directory(directory, filename, as_attachment=True)
