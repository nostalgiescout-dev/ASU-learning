"""routes/messages.py"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session

from kechafa_app.services.message_service import MessageService
from routes.auth import login_required

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")
message_service = MessageService()


@messages_bp.route("/")
@login_required
def inbox():
    uid = session["user_id"]
    inbox_data = message_service.list_inbox(uid)
    requested_thread_id = request.args.get("thread", type=int)
    active_thread_id = requested_thread_id
    active_thread = message_service.get_thread_view(uid, active_thread_id) if active_thread_id else None

    if requested_thread_id and not active_thread:
        flash("Thread not found.", "warning")

    return render_template(
        "messages/inbox.html",
        threads=inbox_data["threads"],
        friends=inbox_data["friends"],
        friend_suggestions=inbox_data["friend_suggestions"],
        instructors=inbox_data["instructors"],
        active_thread=active_thread,
        active_thread_id=active_thread["thread"]["id"] if active_thread else None,
    )


@messages_bp.route("/thread/<int:thread_id>")
@login_required
def thread(thread_id):
    return redirect(url_for("messages.inbox", thread=thread_id))


@messages_bp.route("/send", methods=["POST"])
@login_required
def send():
    uid = session["user_id"]
    receiver_id = request.form.get("receiver_id", type=int)
    body = request.form.get("body", "")
    thread_id = request.form.get("thread_id", type=int)

    result = message_service.send_message(
        user_id=uid,
        receiver_id=receiver_id,
        body=body,
        thread_id=thread_id,
    )
    if not result.ok:
        flash(result.error or "Message could not be sent.", "warning")
        return redirect(request.referrer or url_for("messages.inbox"))

    return redirect(url_for("messages.inbox", thread=result.thread_id))


@messages_bp.route("/direct/<int:user_id>")
@login_required
def direct_chat(user_id):
    uid = session["user_id"]
    result = message_service.open_direct_chat(uid, user_id)
    if not result.ok:
        flash(result.error or "Chat could not be opened.", "warning")
        return redirect(url_for("messages.inbox"))
    return redirect(url_for("messages.inbox", thread=result.thread_id))
