"""Tests for Pydantic models."""

from whaagent.storage.models import Note, ScheduledTask, TaskStatus, TaskType


def test_scheduled_task_defaults() -> None:
    """Test ScheduledTask default values."""
    task = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test",
        action_prompt="test prompt",
        execute_at=1234567890.0,
    )
    assert task.id is not None
    assert len(task.id) > 0
    assert task.status == TaskStatus.PENDING
    assert task.created_at > 0
    assert task.completed_at is None
    assert task.error_message is None
    assert task.cron_expression is None


def test_scheduled_task_to_db_row() -> None:
    """Test converting ScheduledTask to database row."""
    task = ScheduledTask(
        action_type=TaskType.RUN_AGENT,
        action_agent="test",
        action_prompt="test prompt",
        execute_at=1234567890.0,
        cron_expression="* * * * *",
    )
    row = task.to_db_row()
    assert row["id"] == task.id
    assert row["action_type"] == "run_agent"
    assert row["action_agent"] == "test"
    assert row["action_prompt"] == "test prompt"
    assert row["execute_at"] == 1234567890.0
    assert row["cron_expression"] == "* * * * *"
    assert row["status"] == "pending"


def test_scheduled_task_from_db_row() -> None:
    """Test creating ScheduledTask from database row."""
    row = {
        "id": "test-id",
        "action_type": "run_agent",
        "action_agent": "test",
        "action_prompt": "test prompt",
        "execute_at": 1234567890.0,
        "cron_expression": "* * * * *",
        "status": "pending",
        "created_at": 1234567880.0,
        "completed_at": None,
        "error_message": None,
    }
    task = ScheduledTask.from_db_row(row)
    assert task.id == "test-id"
    assert task.action_type == TaskType.RUN_AGENT
    assert task.action_agent == "test"
    assert task.action_prompt == "test prompt"
    assert task.execute_at == 1234567890.0
    assert task.cron_expression == "* * * * *"
    assert task.status == TaskStatus.PENDING


def test_note_defaults() -> None:
    """Test Note default values."""
    note = Note(content="test content")
    assert note.id is not None
    assert len(note.id) > 0
    assert note.created_at > 0


def test_note_to_db_row() -> None:
    """Test converting Note to database row."""
    note = Note(content="test content")
    row = note.to_db_row()
    assert row["id"] == note.id
    assert row["content"] == "test content"
    assert row["created_at"] == note.created_at


def test_note_from_db_row() -> None:
    """Test creating Note from database row."""
    row = {"id": "test-id", "content": "test content", "created_at": 1234567890.0}
    note = Note.from_db_row(row)
    assert note.id == "test-id"
    assert note.content == "test content"
    assert note.created_at == 1234567890.0


def test_task_type_enum() -> None:
    """Test TaskType enum values."""
    assert TaskType.RUN_AGENT == "run_agent"
    assert TaskType.SEND_MESSAGE == "send_message"


def test_task_status_enum() -> None:
    """Test TaskStatus enum values."""
    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.RUNNING == "running"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"
