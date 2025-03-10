from typing import Optional

import discord
from discord import app_commands
from discord.app_commands import Choice

from cronjobs import CRONJOBS


class Cron(app_commands.Group):
    """Manage cron jobs."""

    def __init__(self, client: discord.Client) -> None:
        super().__init__(name="cron")

        self.jobs = {}

        for name, job in CRONJOBS.items():
            job.bind_client(client)
            self.jobs[name] = job.create_task()

    async def _job_autocompletion_func(
        self, _: discord.Interaction, current: str
    ) -> list[Choice[str]]:
        suggestions = []
        for job in self.jobs:
            if current.lower() in job.lower():
                suggestions.append(Choice(name=job, value=job))
            if len(suggestions) == 25:
                break

        return suggestions

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(job=_job_autocompletion_func)  # type: ignore
    async def start(self, interaction: discord.Interaction, job: Optional[str] = None):
        """Start a cron job."""

        if job is None:
            for task in self.jobs.values():
                if not task.is_running():
                    task.start()
            return await interaction.response.send_message(
                "✅ All jobs have been started."
            )

        task = self.jobs.get(job)
        if task is None:
            return await interaction.response.send_message("No such job.")

        if task.is_running():
            return await interaction.response.send_message(
                "This job is already running."
            )

        task.start()
        await interaction.response.send_message(f"✅ Job `{job}` has been started.")

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(job=_job_autocompletion_func)  # type: ignore
    async def stop(self, interaction: discord.Interaction, job: Optional[str] = None):
        """Stop a cron job."""

        if job is None:
            for task in self.jobs.values():
                if task.is_running():
                    task.cancel()
            return await interaction.response.send_message(
                "✅ All jobs have been stopped."
            )

        task = self.jobs.get(job)
        if task is None:
            return await interaction.response.send_message("No such job.")

        if not task.is_running():
            return await interaction.response.send_message(
                "This job is already stopped."
            )

        task.cancel()
        await interaction.response.send_message(f"✅ Job `{job}` has been stopped.")
