"""routes/ai_coach.py - Kachaf AI blueprint."""

from flask import Blueprint, jsonify, render_template, request, session

from kechafa_app.core.security import is_admin_like_user, login_required
from kechafa_app.repositories.user_repository import UserRepository
from kechafa_app.services.ai_service import AIService

ai_bp = Blueprint("ai", __name__, url_prefix="/ai-coach")
ai_service = AIService()
_user_repo = UserRepository()


def _parse_conversation_id(value) -> int | None:
    if value in (None, "", "new"):
        return None
    try:
        conversation_id = int(value)
    except (TypeError, ValueError):
        return None
    return conversation_id if conversation_id > 0 else None


@ai_bp.route("/")
@login_required
def chat_ui():
    uid = session["user_id"]
    requested_conversation_id = _parse_conversation_id(request.args.get("conversation"))
    is_new_chat = request.args.get("new") == "1"

    active_conversation = None if is_new_chat else (
        ai_service.get_conversation(uid, requested_conversation_id)
        if requested_conversation_id
        else ai_service.latest_conversation(uid)
    )
    active_conversation_id = active_conversation["id"] if active_conversation else None
    history = ai_service.get_history(uid, active_conversation_id)

    user_key = session.get("admin_openrouter_key", "")
    return render_template(
        "messages/ai_chat.html",
        history=history,
        ai_status=ai_service.provider_status(user_api_key=user_key),
        conversation_id=active_conversation_id,
        conversation_title=ai_service.get_display_title(uid, active_conversation_id),
        conversations=ai_service.list_conversations(uid),
        has_admin_api_key=bool(user_key),
    )


@ai_bp.route("/send", methods=["POST"])
@login_required
def send_message():
    uid = session["user_id"]
    payload = request.json or {}
    user_input = payload.get("message", "").strip()
    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    conversation_id = _parse_conversation_id(payload.get("conversation_id"))
    user_key = session.get("admin_openrouter_key", "")
    result = ai_service.reply(uid, user_input, conversation_id, user_api_key=user_key)
    if not result["ok"]:
        return (
            jsonify(
                {
                    "error": result["reason"],
                    "conversation_id": result["conversation_id"],
                    "provider": result["provider"],
                    "provider_label": result["label"],
                    "is_live": result["is_live"],
                    "provider_reason": result["reason"],
                }
            ),
            503,
        )

    return jsonify(
        {
            "reply": result["reply"],
            "conversation_id": result["conversation_id"],
            "conversation_title": result["conversation_title"],
            "provider": result["provider"],
            "provider_label": result["label"],
            "is_live": result["is_live"],
            "provider_reason": result["reason"],
        }
    )


@ai_bp.route("/clear", methods=["POST"])
@login_required
def clear():
    payload = request.json or {}
    conversation_id = _parse_conversation_id(payload.get("conversation_id"))
    ai_service.clear_history(session["user_id"], conversation_id)
    return jsonify({"status": "cleared"})


@ai_bp.route("/rename", methods=["POST"])
@login_required
def rename():
    payload = request.json or {}
    conversation_id = _parse_conversation_id(payload.get("conversation_id"))
    renamed = ai_service.rename_conversation(
        session["user_id"],
        conversation_id,
        payload.get("title", ""),
    )
    if not renamed:
        return jsonify({"error": "Conversation could not be renamed."}), 400
    return jsonify({"status": "renamed", **renamed})


@ai_bp.route("/delete", methods=["POST"])
@login_required
def delete():
    payload = request.json or {}
    conversation_id = _parse_conversation_id(payload.get("conversation_id"))
    deleted = ai_service.delete_conversation(session["user_id"], conversation_id)
    if not deleted:
        return jsonify({"error": "Conversation could not be deleted."}), 404
    return jsonify({"status": "deleted", "conversation_id": conversation_id})


@ai_bp.route("/set-api-key", methods=["POST"])
@login_required
def set_api_key():
    user = _user_repo.get_by_id(session["user_id"])
    if not is_admin_like_user(user):
        return jsonify({"error": "Forbidden"}), 403
    payload = request.json or {}
    api_key = (payload.get("api_key") or "").strip()
    if api_key:
        session["admin_openrouter_key"] = api_key
    else:
        session.pop("admin_openrouter_key", None)
    session.modified = True
    user_key = session.get("admin_openrouter_key", "")
    status = ai_service.provider_status(user_api_key=user_key)
    return jsonify({
        "status": "saved",
        "has_key": bool(user_key),
        "provider_label": status["label"],
        "is_live": status["is_live"],
        "provider_reason": status["reason"],
    })


@ai_bp.route("/edit-message", methods=["POST"])
@login_required
def edit_message():
    payload = request.json or {}
    conversation_id = _parse_conversation_id(payload.get("conversation_id"))
    message_index = payload.get("message_index")
    try:
        message_index = int(message_index)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid message index."}), 400

    user_key = session.get("admin_openrouter_key", "")
    result = ai_service.edit_user_message(
        session["user_id"],
        conversation_id,
        message_index,
        payload.get("message", ""),
        user_api_key=user_key,
    )
    if not result["ok"]:
        return jsonify({"error": result["reason"]}), 400

    return jsonify(
        {
            "status": "updated",
            "conversation_id": result["conversation_id"],
            "conversation_title": result["conversation_title"],
            "provider_label": result["label"],
            "is_live": result["is_live"],
            "provider_reason": result["reason"],
        }
    )
