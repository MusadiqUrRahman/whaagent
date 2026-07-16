"""Tests for Database class."""

from pathlib import Path

import pytest

from whaagent.storage.database import Database


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path: Path) -> Database:
    """Create a Database instance."""
    db = Database(db_path)
    yield db
    db.close()


def test_database_init(db: Database, db_path: Path) -> None:
    """Test database initialization."""
    assert db._db_path == db_path
    assert db_path.exists()


def test_connection_thread_local(db: Database) -> None:
    """Test that each thread gets its own connection."""
    import threading

    connections = []

    def get_connection() -> None:
        conn = db.connection
        connections.append(id(conn))

    t1 = threading.Thread(target=get_connection)
    t2 = threading.Thread(target=get_connection)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(connections) == 2
    assert connections[0] != connections[1]


def test_schema_created(db: Database) -> None:
    """Test that tables are created."""
    cursor = db.connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "scheduled_tasks" in tables
    assert "notes" in tables


def test_indexes_created(db: Database) -> None:
    """Test that indexes are created."""
    cursor = db.connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name",
    )
    indexes = [row[0] for row in cursor.fetchall()]
    assert "idx_scheduled_execute_at" in indexes
    assert "idx_scheduled_status" in indexes
    assert "idx_notes_created_at" in indexes


def test_close(db: Database) -> None:
    """Test closing the connection."""
    _ = db.connection
    assert db._local.conn is not None
    db.close()
    assert db._local.conn is None
