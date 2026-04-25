"""Blueprint registration layer for the upgraded application package."""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from routes.admin import admin_bp
    from routes.ai_coach import ai_bp
    from routes.auth import auth_bp
    from routes.content.views import content_bp
    from routes.courses import courses_bp
    from routes.dashboard import dashboard_bp
    from routes.library import library_bp
    from routes.messages import messages_bp
    from routes.notifications import notifications_bp
    from routes.misc import misc_bp
    from routes.profile import profile_bp
    from routes.contact import contact_bp

    for bp in [auth_bp, dashboard_bp, profile_bp, courses_bp, messages_bp, notifications_bp, ai_bp, admin_bp, misc_bp, library_bp, contact_bp]:
        app.register_blueprint(bp)
    app.register_blueprint(content_bp)

