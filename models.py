from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()


def init_models(app) -> None:
    """Bind Flask-SQLAlchemy using the app's configured database URL."""
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", app.config.get("DATABASE_URL", "sqlite:///kechafa.db"))
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)


class ContactSubmission(db.Model):
    __tablename__ = "contact_submissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", server_default=text("'pending'"))
    is_verified = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))
    verified_at = db.Column(db.DateTime)

    def mark_verified(self) -> None:
        self.is_verified = True
        self.status = "verified"
        self.verified_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<ContactSubmission id={self.id} email={self.email!r} status={self.status!r}>"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(512), server_default=text("'https://api.dicebear.com/7.x/thumbs/svg?seed=kechafa'"))
    country = db.Column(db.String(120))
    scout_unit = db.Column(db.String(255))
    role = db.Column(db.String(50), nullable=False, server_default=text("'scout'"))
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=text("1"))
    level_points = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))
    level_rank = db.Column(db.Integer, nullable=False, default=1, server_default=text("1"))
    streak_days = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))
    total_reels_watched = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))
    preferred_lang = db.Column(db.String(8), nullable=False, default="en", server_default=text("'en'"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    taught_courses = db.relationship("Course", back_populates="instructor", foreign_keys="Course.instructor_id")
    created_course_categories = db.relationship("CourseCategory", back_populates="creator", foreign_keys="CourseCategory.created_by")
    created_book_categories = db.relationship("BookCategory", back_populates="creator", foreign_keys="BookCategory.created_by")
    uploaded_books = db.relationship("Book", back_populates="uploader", foreign_keys="Book.uploaded_by")
    uploaded_videos = db.relationship("Video", back_populates="uploader", foreign_keys="Video.uploader_id")
    comments = db.relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    likes = db.relationship("Like", back_populates="user", cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")
    badge_links = db.relationship("UserBadge", back_populates="user", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    ai_conversations = db.relationship("AIConversation", back_populates="user", cascade="all, delete-orphan")
    owned_groups = db.relationship("CommunityGroup", back_populates="owner", foreign_keys="CommunityGroup.owner_id")
    group_links = db.relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    sent_messages = db.relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    received_messages = db.relationship("Message", back_populates="receiver", foreign_keys="Message.receiver_id")
    primary_threads = db.relationship("Thread", back_populates="participant_a_user", foreign_keys="Thread.participant_a")
    secondary_threads = db.relationship("Thread", back_populates="participant_b_user", foreign_keys="Thread.participant_b")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    title_ar = db.Column(db.String(255))
    description = db.Column(db.Text)
    thumbnail_url = db.Column(db.String(512))
    category = db.Column(db.String(120), nullable=False, default="general", server_default=text("'general'"))
    difficulty = db.Column(db.String(50), nullable=False, default="beginner", server_default=text("'beginner'"))
    xp_reward = db.Column(db.Integer, nullable=False, default=500, server_default=text("500"))
    duration_mins = db.Column(db.Integer)
    is_published = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    is_featured = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    instructor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    instructor = db.relationship("User", back_populates="taught_courses", foreign_keys=[instructor_id])
    videos = db.relationship("Video", back_populates="course", order_by="Video.order_index")
    enrollments = db.relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Course id={self.id} title={self.title!r}>"


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(512), nullable=False)
    language = db.Column(db.String(8), nullable=False, default="en", server_default=text("'en'"))
    category_id = db.Column(db.Integer, db.ForeignKey("book_categories.id"))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    category = db.relationship("BookCategory", back_populates="books")
    uploader = db.relationship("User", back_populates="uploaded_books", foreign_keys=[uploaded_by])

    def __repr__(self) -> str:
        return f"<Book id={self.id} title={self.title!r}>"


class BookCategory(db.Model):
    __tablename__ = "book_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    creator = db.relationship("User", back_populates="created_book_categories", foreign_keys=[created_by])
    books = db.relationship("Book", back_populates="category")

    def __repr__(self) -> str:
        return f"<BookCategory id={self.id} name={self.name!r}>"


class CourseCategory(db.Model):
    __tablename__ = "course_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    emoji = db.Column(db.String(16), nullable=False, default="📚", server_default=text("'📚'"))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    creator = db.relationship("User", back_populates="created_course_categories", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<CourseCategory id={self.id} slug={self.slug!r}>"


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (
        db.UniqueConstraint("user_id", "course_id", name="uq_enrollments_user_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    progress_pct = db.Column(db.Float, nullable=False, default=0.0, server_default=text("0.0"))
    is_completed = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    enrolled_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))
    completed_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")

    def __repr__(self) -> str:
        return f"<Enrollment user_id={self.user_id} course_id={self.course_id}>"


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    title_ar = db.Column(db.String(255))
    description = db.Column(db.Text)
    video_url = db.Column(db.String(1024), nullable=False)
    thumbnail_url = db.Column(db.String(512))
    video_type = db.Column(db.String(50), nullable=False, default="reel", server_default=text("'reel'"))
    category = db.Column(db.String(120), nullable=False, default="general", server_default=text("'general'"))
    duration_secs = db.Column(db.Integer)
    order_index = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))
    view_count = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))
    xp_reward = db.Column(db.Integer, nullable=False, default=50, server_default=text("50"))
    is_published = db.Column(db.Boolean, nullable=False, default=True, server_default=text("1"))
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    uploader = db.relationship("User", back_populates="uploaded_videos", foreign_keys=[uploader_id])
    course = db.relationship("Course", back_populates="videos")
    comments = db.relationship("Comment", back_populates="video", cascade="all, delete-orphan")
    likes = db.relationship("Like", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Video id={self.id} title={self.title!r} type={self.video_type!r}>"


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    author = db.relationship("User", back_populates="comments")
    video = db.relationship("Video", back_populates="comments")

    def __repr__(self) -> str:
        return f"<Comment id={self.id} author_id={self.author_id} video_id={self.video_id}>"


class Like(db.Model):
    __tablename__ = "likes"
    __table_args__ = (
        db.UniqueConstraint("user_id", "video_id", name="uq_likes_user_video"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)

    user = db.relationship("User", back_populates="likes")
    video = db.relationship("Video", back_populates="likes")

    def __repr__(self) -> str:
        return f"<Like user_id={self.user_id} video_id={self.video_id}>"


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    icon = db.Column(db.String(64), nullable=False, default="🏅", server_default=text("'🏅'"))
    color = db.Column(db.String(32), nullable=False, default="#f59e0b", server_default=text("'#f59e0b'"))
    description = db.Column(db.Text)
    xp_value = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))

    user_links = db.relationship("UserBadge", back_populates="badge", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Badge id={self.id} name={self.name!r}>"


class UserBadge(db.Model):
    __tablename__ = "user_badges"
    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_id", name="uq_user_badges_user_badge"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id"), nullable=False)
    awarded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    user = db.relationship("User", back_populates="badge_links")
    badge = db.relationship("Badge", back_populates="user_links")

    def __repr__(self) -> str:
        return f"<UserBadge user_id={self.user_id} badge_id={self.badge_id}>"


class Thread(db.Model):
    __tablename__ = "threads"

    id = db.Column(db.Integer, primary_key=True)
    participant_a = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    participant_b = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_ai_thread = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    participant_a_user = db.relationship("User", back_populates="primary_threads", foreign_keys=[participant_a])
    participant_b_user = db.relationship("User", back_populates="secondary_threads", foreign_keys=[participant_b])
    messages = db.relationship("Message", back_populates="thread", cascade="all, delete-orphan", order_by="Message.created_at")

    def __repr__(self) -> str:
        return f"<Thread id={self.id} participant_a={self.participant_a} participant_b={self.participant_b}>"


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    thread_id = db.Column(db.Integer, db.ForeignKey("threads.id"))
    is_ai_message = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    sender = db.relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
    receiver = db.relationship("User", back_populates="received_messages", foreign_keys=[receiver_id])
    thread = db.relationship("Thread", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} sender_id={self.sender_id} thread_id={self.thread_id}>"


class AIConversation(db.Model):
    __tablename__ = "ai_conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    history_json = db.Column(db.Text, nullable=False, default="[]", server_default=text("'[]'"))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    user = db.relationship("User", back_populates="ai_conversations")

    def __repr__(self) -> str:
        return f"<AIConversation id={self.id} user_id={self.user_id}>"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(50), nullable=False, default="info", server_default=text("'info'"))
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text)
    icon = db.Column(db.String(64), nullable=False, default="🔔", server_default=text("'🔔'"))
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default=text("0"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user_id={self.user_id} kind={self.kind!r}>"


class CommunityGroup(db.Model):
    __tablename__ = "community_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    region = db.Column(db.String(120))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=text("(datetime('now'))"))

    owner = db.relationship("User", back_populates="owned_groups", foreign_keys=[owner_id])
    members = db.relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CommunityGroup id={self.id} name={self.name!r}>"


class GroupMember(db.Model):
    __tablename__ = "group_members"

    group_id = db.Column(db.Integer, db.ForeignKey("community_groups.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)

    group = db.relationship("CommunityGroup", back_populates="members")
    user = db.relationship("User", back_populates="group_links")

    def __repr__(self) -> str:
        return f"<GroupMember group_id={self.group_id} user_id={self.user_id}>"


__all__ = [
    "db",
    "init_models",
    "AIConversation",
    "Badge",
    "Book",
    "BookCategory",
    "Comment",
    "CommunityGroup",
    "Course",
    "CourseCategory",
    "Enrollment",
    "GroupMember",
    "Like",
    "Message",
    "Notification",
    "Thread",
    "User",
    "UserBadge",
    "Video",
]
