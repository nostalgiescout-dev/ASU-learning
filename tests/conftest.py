import pytest


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    import database
    db_file = str(tmp_path / "test.db")
    database.DB_PATH = db_file
    from database import init_db
    init_db()
