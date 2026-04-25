from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from kechafa_app.services.notification_service import NotificationService
from routes.auth import login_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")
notification_service = NotificationService()


@notifications_bp.route("/")
@login_required
def index():
    unread_only = request.args.get("filter") == "unread"
    items = notification_service.list_for_user(session["user_id"], unread_only=unread_only)
    return render_template("notifications/index.html", notifications=items, unread_only=unread_only)


@notifications_bp.route("/<int:notification_id>/open")
@login_required
def open_notification(notification_id: int):
    item = notification_service.get_for_user(session["user_id"], notification_id)
    if not item:
        flash("Notification not found.", "warning")
        return redirect(url_for("notifications.index"))

    notification_service.mark_read(session["user_id"], notification_id)
    return redirect(item.get("target_url") or url_for("notifications.index"))


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id: int):
    notification_service.mark_read(session["user_id"], notification_id)
    return redirect(request.referrer or url_for("notifications.index"))


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    notification_service.mark_all_read(session["user_id"])
    flash("All notifications marked as read.", "success")
    return redirect(request.referrer or url_for("notifications.index"))
