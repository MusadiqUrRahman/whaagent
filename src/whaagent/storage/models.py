"""Pydantic models for scheduled tasks and notes."""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task action types."""

    RUN_AGENT = "run_agent"
    SEND_MESSAGE = "send_message"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScheduledTask(BaseModel):
    """A scheduled task for execution."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: TaskType
    action_agent: str | None = None
    action_prompt: str | None = None
    context_id: str | None = None  # Optional context ID (e.g. thread_id, user_id)
    execute_at: float
    cron_expression: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = Field(default_factory=lambda: datetime.now(UTC).timestamp())
    completed_at: float | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None

    def to_db_row(self) -> dict[str, Any]:
        """Convert to database row format."""
        return {
            "id": self.id,
            "action_type": self.action_type.value,
            "action_agent": self.action_agent,
            "action_prompt": self.action_prompt,
            "context_id": self.context_id,
            "execute_at": self.execute_at,
            "cron_expression": self.cron_expression,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "ScheduledTask":
        """Create from database row."""
        return cls(
            id=row["id"],
            action_type=TaskType(row["action_type"]),
            action_agent=row["action_agent"],
            action_prompt=row["action_prompt"],
            context_id=row.get("context_id"),
            execute_at=row["execute_at"],
            cron_expression=row["cron_expression"],
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
            metadata=row.get("metadata"),
        )


class Note(BaseModel):
    """A simple note stored in the database."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    context_id: str | None = None  # Optional context ID (e.g. thread_id, user_id)
    content: str
    created_at: float = Field(default_factory=lambda: datetime.now(UTC).timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now(UTC).timestamp())

    def to_db_row(self) -> dict[str, Any]:
        """Convert to database row format."""
        return {
            "id": self.id,
            "context_id": self.context_id,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "Note":
        """Create from database row."""
        return cls(
            id=row["id"],
            context_id=row.get("context_id"),
            content=row["content"],
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
        )
