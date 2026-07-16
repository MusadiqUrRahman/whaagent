"""Repository for notes."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whaagent.storage.database import Database
    from whaagent.storage.models import Note

logger = logging.getLogger(__name__)


class NoteRepository:
    """Repository for managing notes in the database."""

    def __init__(self, db: "Database") -> None:
        """Initialize the repository.

        Args:
            db: Database connection instance.
        """
        self._db = db

    def save(self, note: "Note") -> "Note":
        """Save a note to the database.

        Args:
            note: Note to save.

        Returns:
            The saved note.
        """
        conn = self._db.connection
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO notes (id, context_id, content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (note.id, note.context_id, note.content, note.created_at, note.updated_at),
        )
        conn.commit()
        logger.debug(f"Saved note: {note.id}")
        return note

    def get_by_id(self, note_id: str) -> "Note | None":
        """Get a note by ID.

        Args:
            note_id: Note ID.

        Returns:
            Note instance or None if not found.
        """
        conn = self._db.connection
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_note(dict(row))

    def list_all(self) -> list["Note"]:
        """Get all notes ordered by creation time.

        Returns:
            List of all notes.
        """
        conn = self._db.connection
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes ORDER BY created_at ASC")
        return [self._row_to_note(dict(row)) for row in cursor.fetchall()]

    def delete(self, note_id: str) -> bool:
        """Delete a note by ID.

        Args:
            note_id: Note ID.

        Returns:
            True if deleted, False if not found.
        """
        conn = self._db.connection
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"Deleted note: {note_id}")
        return deleted

    def _row_to_note(self, row: dict[str, object]) -> "Note":
        """Convert database row to Note.

        Args:
            row: Database row as dictionary.

        Returns:
            Note instance.
        """
        from whaagent.storage.models import Note

        return Note.from_db_row(row)
