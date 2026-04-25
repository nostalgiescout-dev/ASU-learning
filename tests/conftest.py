import os
import pytest

os.environ.setdefault("KECHAFA_DB", ":memory:")


@pytest.fixture(autouse=True)
def setup_db():
    import database
    database.DB_PATH = ":memory:"
    from database import init_db
    init_db()
