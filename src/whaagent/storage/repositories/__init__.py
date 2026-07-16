"""Repository layer for database access."""

from whaagent.storage.repositories.note_repository import NoteRepository
from whaagent.storage.repositories.task_repository import TaskRepository

__all__ = ["NoteRepository", "TaskRepository"]
