"""Background task management for Eruditus."""

import traceback
from typing import TYPE_CHECKING, Callable, List

from discord.ext import tasks

if TYPE_CHECKING:
    from eruditus import Eruditus


class TaskManager:
    """Manages background tasks for the Discord bot.

    This class provides a centralized way to register, start, and manage
    all background tasks that the bot needs to run.
    """

    def __init__(self, client: "Eruditus") -> None:
        """Initialize the task manager.

        Args:
            client: The Discord bot client instance.
        """
        self.client = client
        self._tasks: List[tasks.Loop] = []

    def register(self, task: tasks.Loop) -> tasks.Loop:
        """Register a task to be managed.

        Args:
            task: The task loop to register.

        Returns:
            The registered task.
        """
        self._tasks.append(task)
        return task

    def start_all(self) -> None:
        """Start all registered tasks."""
        for task in self._tasks:
            if not task.is_running():
                task.start()

    def stop_all(self) -> None:
        """Stop all registered tasks."""
        for task in self._tasks:
            if task.is_running():
                task.cancel()


def create_error_handler(task: tasks.Loop) -> Callable:
    """Create a standard error handler for a task.

    Args:
        task: The task loop to create an error handler for.

    Returns:
        An async error handler function.
    """

    async def error_handler(error: Exception) -> None:
        traceback.print_exc()
        task.restart()

    return error_handler
