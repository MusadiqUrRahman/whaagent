"""Thread-safe SQLite database connection."""

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

# Flag to track if schema has been initialized globally
_schema_initialized: threading.Event | None = None
_schema_lock = threading.Lock()


def _ensure_schema_initialized() -> None:
    """Ensure schema is initialized exactly once across all threads."""
    global _schema_initialized

    if _schema_initialized is None:
        with _schema_lock:
            if _schema_initialized is None:
                _schema_initialized = threading.Event()
            elif _schema_initialized.is_set():
                return

    if not _schema_initialized.is_set():
        _schema_initialized.set()


class Database:
    """Thread-safe SQLite database connection.

    Each thread gets its own connection to avoid SQLite threading issues.
    Follows the pattern from youtube_cache.py.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the database.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path
        self._local = threading.local()
        self._ensure_db_dir()
        self._init_database()

    def _ensure_db_dir(self) -> None:
        """Create database directory if it doesn't exist."""
        # Only create if it doesn't exist (avoid unnecessary I/O)
        if not self._db_path.parent.exists():
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Database path: {self._db_path}")

    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection.

        Returns:
            A SQLite connection for the current thread.
        """
        if not hasattr(self._local, "conn") or self._local.conn is None:
            _ensure_schema_initialized()
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            # Only initialize schema once per process, not per thread
            if not hasattr(self._local, "schema_inited"):
                self._init_schema(self._local.conn)
                self._local.schema_inited = True
            logger.debug(f"Created thread-local DB connection for thread {threading.get_ident()}")
        return cast(sqlite3.Connection, self._local.conn)

    def get_checkpointer(self, is_async: bool = False) -> Any:
        """Get a LangGraph checkpointer using this database.

        WARNING: For async usage, call get_async_checkpointer() instead.
        The sync SqliteSaver does not support async methods needed
        by LangGraph's async runtime. AsyncSqliteSaver requires
        using its async context manager (AsyncSqliteSaver.from_conn_string).

        Args:
            is_async: Deprecated. Use get_async_checkpointer() for async agents.

        Returns:
            A sync SqliteSaver (only works with sync LangGraph agents).
        """
        from langgraph.checkpoint.sqlite import SqliteSaver

        return SqliteSaver(self.connection)

    async def get_async_checkpointer(self) -> Any:
        """Get an async-compatible LangGraph checkpointer.

        Returns an async context manager yielding AsyncSqliteSaver.
        Use as: ``async with db.get_async_checkpointer() as cp:``

        Example:
            ```python
            db = Database(Path("checkpoints.db"))
            async with await db.get_async_checkpointer() as checkpointer:
                agent = MyAgent(checkpointer=checkpointer, ...)
            ```
        """
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        return AsyncSqliteSaver.from_conn_string(str(self._db_path))

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Initialize the database schema."""
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                action_agent TEXT,
                action_prompt TEXT,
                context_id TEXT,
                execute_at REAL NOT NULL,
                cron_expression TEXT,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                completed_at REAL,
                error_message TEXT
            )
        """)

        # Schema migrations for scheduled_tasks
        cursor.execute("PRAGMA table_info(scheduled_tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        if "context_id" not in columns:
            cursor.execute("ALTER TABLE scheduled_tasks ADD COLUMN context_id TEXT")
        if "metadata" not in columns:
            cursor.execute("ALTER TABLE scheduled_tasks ADD COLUMN metadata TEXT")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_execute_at
            ON scheduled_tasks(execute_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_status
            ON scheduled_tasks(status)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                context_id TEXT,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)

        # Schema migrations for notes
        cursor.execute("PRAGMA table_info(notes)")
        columns = [row[1] for row in cursor.fetchall()]
        if "context_id" not in columns:
            cursor.execute("ALTER TABLE notes ADD COLUMN context_id TEXT")
        if "updated_at" not in columns:
            cursor.execute("ALTER TABLE notes ADD COLUMN updated_at REAL DEFAULT 0")
            cursor.execute("UPDATE notes SET updated_at = created_at WHERE updated_at = 0")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_created_at
            ON notes(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_context_at
            ON notes(context_id)
        """)
        conn.commit()

    def _init_database(self) -> None:
        """Initialize database connection."""
        try:
            self.connection
            logger.info(f"Initialized database: {self._db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def close(self) -> None:
        """Close database connection for the current thread."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {e}")
            self._local.conn = None
            logger.debug("Closed database connection")
