"""Tests for repository classes."""

import time
from pathlib import Path

import pytest

from whaagent.storage import Database, Note, NoteRepository, ScheduledTask, TaskRepository
from whaagent.storage.models import TaskStatus, TaskType


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


@pytest.fixture
def task_repo(db: Database) -> TaskRepository:
    """Create a TaskRepository instance."""
    return TaskRepository(db)


@pytest.fixture
def note_repo(db: Database) -> NoteRepository:
    """Create a NoteRepository instance."""
    return NoteRepository(db)


def test_task_repository_save(task_repo: TaskRepository) -> None:
    """Test saving a task."""
    task = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test",
        action_prompt="test prompt",
        execute_at=time.time() + 3600,
    )
    saved = task_repo.save(task)
    assert saved.id == task.id


def test_task_repository_get_by_id(task_repo: TaskRepository) -> None:
    """Test getting a task by ID."""
    task = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test",
        action_prompt="test prompt",
        execute_at=time.time() + 3600,
    )
    task_repo.save(task)
    retrieved = task_repo.get_by_id(task.id)
    assert retrieved is not None
    assert retrieved.id == task.id
    assert retrieved.action_agent == "test"


def test_task_repository_get_by_id_not_found(task_repo: TaskRepository) -> None:
    """Test getting a non-existent task."""
    retrieved = task_repo.get_by_id("non-existent")
    assert retrieved is None


def test_task_repository_get_due_tasks(task_repo: TaskRepository) -> None:
    """Test getting due tasks."""
    now = time.time()
    task1 = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test1",
        execute_at=now - 100,  # Past
    )
    task2 = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test2",
        execute_at=now + 3600,  # Future
    )
    task_repo.save(task1)
    task_repo.save(task2)

    due_tasks = task_repo.get_due_tasks()
    assert len(due_tasks) == 1
    assert due_tasks[0].id == task1.id


def test_task_repository_update_status(task_repo: TaskRepository) -> None:
    """Test updating task status."""
    task = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test",
        action_prompt="test prompt",
        execute_at=time.time() + 3600,
    )
    task_repo.save(task)

    updated = task_repo.update_status(task.id, "completed")
    assert updated is True

    retrieved = task_repo.get_by_id(task.id)
    assert retrieved is not None
    assert retrieved.status == TaskStatus.COMPLETED


def test_task_repository_update_status_with_error(task_repo: TaskRepository) -> None:
    """Test updating task status with error message."""
    task = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test",
        execute_at=time.time() + 3600,
    )
    task_repo.save(task)

    updated = task_repo.update_status(task.id, "failed", error_message="test error")
    assert updated is True

    retrieved = task_repo.get_by_id(task.id)
    assert retrieved is not None
    assert retrieved.status == TaskStatus.FAILED
    assert retrieved.error_message == "test error"


def test_task_repository_update_status_not_found(task_repo: TaskRepository) -> None:
    """Test updating non-existent task status."""
    updated = task_repo.update_status("non-existent", "completed")
    assert updated is False


def test_note_repository_save(note_repo: NoteRepository) -> None:
    """Test saving a note."""
    note = Note(content="test content")
    saved = note_repo.save(note)
    assert saved.id == note.id


def test_note_repository_get_by_id(note_repo: NoteRepository) -> None:
    """Test getting a note by ID."""
    note = Note(content="test content")
    note_repo.save(note)
    retrieved = note_repo.get_by_id(note.id)
    assert retrieved is not None
    assert retrieved.id == note.id
    assert retrieved.content == "test content"


def test_note_repository_list_all(note_repo: NoteRepository) -> None:
    """Test listing all notes."""
    note1 = Note(content="first")
    note2 = Note(content="second")
    note_repo.save(note1)
    note_repo.save(note2)

    notes = note_repo.list_all()
    assert len(notes) == 2
    assert notes[0].content == "first"
    assert notes[1].content == "second"


def test_note_repository_delete(note_repo: NoteRepository) -> None:
    """Test deleting a note."""
    note = Note(content="test content")
    note_repo.save(note)

    deleted = note_repo.delete(note.id)
    assert deleted is True

    retrieved = note_repo.get_by_id(note.id)
    assert retrieved is None


def test_note_repository_delete_not_found(note_repo: NoteRepository) -> None:
    """Test deleting a non-existent note."""
    deleted = note_repo.delete("non-existent")
    assert deleted is False
