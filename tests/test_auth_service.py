from kechafa_app.services.auth_service import AuthService


def test_validate_registration_rejects_short_username():
    service = AuthService()
    errors = service.validate_registration("ab", "user@example.com", "secret123")
    assert "Username must be at least 3 characters." in errors


def test_validate_registration_rejects_bad_email():
    service = AuthService()
    errors = service.validate_registration("scoutuser", "bad-email", "secret123")
    assert "Valid email required." in errors
