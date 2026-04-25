"""Centralized error handling for HTML and JSON requests."""

from __future__ import annotations

from flask import current_app, jsonify, render_template, request


JSON_MIMETYPES = {"application/json", "application/vnd.api+json"}


def _wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best
    return best in JSON_MIMETYPES


def register_error_handlers(app) -> None:
    @app.errorhandler(400)
    def bad_request(error):
        if _wants_json():
            return jsonify({"error": "bad_request", "message": str(error)}), 400
        return render_template("errors/403.html"), 400

    @app.errorhandler(403)
    def forbidden(error):
        if _wants_json():
            return jsonify({"error": "forbidden", "message": str(error)}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json():
            return jsonify({"error": "not_found", "message": "Resource not found."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def request_too_large(error):
        max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 0)
        max_mb = max(1, round(max_bytes / (1024 * 1024))) if max_bytes else None
        if _wants_json():
            return jsonify({
                "error": "request_too_large",
                "message": f"Uploaded file is too large. Maximum allowed size is {max_mb} MB." if max_mb else "Uploaded file is too large.",
            }), 413
        return render_template("errors/413.html", max_mb=max_mb), 413

    @app.errorhandler(500)
    def server_error(error):
        if _wants_json():
            return jsonify({"error": "server_error", "message": "Unexpected server error."}), 500
        return render_template("errors/404.html"), 500
