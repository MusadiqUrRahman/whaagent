"""Cron module for executing scheduled tasks."""

import asyncio
import logging

from whaagent_storage import Database, TaskRepository, calculate_next_run
from whaagent_storage.models import ScheduledTask, TaskStatus, TaskType  # type: ignore

from whaagent.constants import STORAGE_DIR
from whaagent.registry import AgentRegistry

logger = logging.getLogger(__name__)

# Database path
DB_PATH = STORAGE_DIR / "whaagent" / "tasks.db"


def tick() -> int:
    """Execute all due tasks.

    Returns:
        Number of tasks executed.
    """
    db = Database(DB_PATH)
    task_repo = TaskRepository(db)

    try:
        due_tasks = task_repo.get_due_tasks()
        logger.info(f"Found {len(due_tasks)} due tasks")

        executed = 0
        for task in due_tasks:
            try:
                execute_task(task, task_repo)
                executed += 1
            except Exception as e:
                logger.error(f"Error executing task {task.id}: {e}")
                task_repo.update_status(
                    task.id,
                    TaskStatus.FAILED,
                    error_message=str(e),
                )

        return executed
    finally:
        db.close()


def execute_task(
    task: ScheduledTask,
    task_repo: TaskRepository,
) -> None:
    """Execute a single task.

    Args:
        task: Task to execute.
        task_repo: Task repository for updates.
    """
    logger.info(f"Executing task {task.id}: {task.action_type}")

    # Update status to running
    task_repo.update_status(task.id, TaskStatus.RUNNING)

    if task.action_type == TaskType.RUN_AGENT:
        _run_agent_task(task)
    elif task.action_type == TaskType.SEND_MESSAGE:
        _send_message_task(task)
    else:
        raise ValueError(f"Unknown action type: {task.action_type}")

    # For recurring tasks, schedule next run
    if task.cron_expression:
        next_run = calculate_next_run(task.cron_expression)
        next_task = ScheduledTask(
            action_type=task.action_type,
            action_agent=task.action_agent,
            action_prompt=task.action_prompt,
            execute_at=next_run.timestamp(),
            cron_expression=task.cron_expression,
        )
        task_repo.save(next_task)
        logger.info(f"Scheduled next run for {task.id}: {next_run}")

    # Mark current task as completed
    task_repo.update_status(task.id, TaskStatus.COMPLETED)


def _run_agent_task(task: ScheduledTask) -> str:
    """Run an agent task.

    Args:
        task: Task with agent name and prompt.

    Returns:
        Agent output.
    """
    if not task.action_agent:
        raise ValueError("run_agent task requires action_agent")

    agent_cls = AgentRegistry.get(task.action_agent)
    if not agent_cls:
        raise ValueError(f"Agent not found: {task.action_agent}")

    prompt = task.action_prompt or ""
    result = asyncio.run(agent_cls().run(prompt))
    result_str = str(result)
    logger.info(f"Agent {task.action_agent} output: {result_str[:100]}...")
    return result_str


def _send_message_task(task: ScheduledTask) -> str:
    """Send a message task.

    Args:
        task: Task with message content.

    Returns:
        Result message.
    """
    # WhatsApp messaging would be implemented here
    # For now, log the message
    message = task.action_prompt or ""
    logger.info(f"Would send message: {message}")
    return f"Message sent: {message}"
