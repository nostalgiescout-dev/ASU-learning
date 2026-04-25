import pytest


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    import database
    db_file = str(tmp_path / "test.db")
    database.DB_PATH = db_file

    from kechafa_app import create_app
    app = create_app("testing", config_overrides={"KECHAFA_DB": db_file})

    with app.app_context():
        from database import init_db
        init_db()
        yield
