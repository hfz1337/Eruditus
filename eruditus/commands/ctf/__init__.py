"""CTF command group - manages CTF competitions."""

import asyncio
import logging
import subprocess
import tempfile
from datetime import datetime
from typing import Optional

import discord
from aiohttp.client_exceptions import ClientError, InvalidURL
from bson import ObjectId
from components.buttons.workon import WorkonButton
from components.modals.credentials import create_credentials_modal_for_platform
from components.modals.flag import FlagSubmissionForm
from config import DATE_FORMAT, MAX_CONTENT_SIZE, TEAM_NAME
from constants import (
    MAX_AUTOCOMPLETE_CHOICES,
    MAX_EMBED_FIELDS,
    ChannelNames,
    EmbedColours,
    Emojis,
    ErrorMessages,
    ThreadPrefixes,
)
from db.challenge_repository import ChallengeRepository
from db.ctf_repository import CTFRepository
from discord import app_commands
from discord.app_commands import Choice
from models.enums import CTFStatusMode, Permissions, Privacy
from platforms import PlatformCTX, match_platform
from services import ScoreboardService
from utils.discord import (
    add_challenge_worker,
    get_challenge_category_channel,
    mark_if_maxed,
    parse_challenge_solvers,
    parse_member_mentions,
    remove_challenge_worker,
)
from utils.formatting import sanitize_channel_name
from utils.http import strip_url_components
from utils.responses import send_error, send_response

_log = logging.getLogger(__name__)
_ctf_repo = CTFRepository()
_challenge_repo = ChallengeRepository()
_scoreboard_service = ScoreboardService()


def _in_ctf_channel():
    """Check if command was issued from a CTF channel."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id):
            return True
        await send_response(
            interaction, "You must be in a CTF channel to use this command."
        )
        return False

    return app_commands.check(predicate)


async def _ctf_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[Choice[str]]:
    """Autocomplete CTF name."""
    suggestions = []
    for ctf in _ctf_repo.find_active():
        if current.lower() in ctf["name"].lower():
            suggestions.append(Choice(name=ctf["name"], value=ctf["name"]))
        if len(suggestions) == MAX_AUTOCOMPLETE_CHOICES:
            break
    return suggestions


async def _challenge_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[Choice[str]]:
    """Autocomplete challenge name (unsolved only)."""
    return await _challenge_autocomplete_impl(interaction, current, unsolved_only=True)


async def _all_challenges_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[Choice[str]]:
    """Autocomplete challenge name (all challenges)."""
    return await _challenge_autocomplete_impl(interaction, current, unsolved_only=False)


async def _challenge_autocomplete_impl(
    interaction: discord.Interaction, current: str, *, unsolved_only: bool
) -> list[Choice[str]]:
    """Autocomplete challenge name implementation."""
    ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
    if ctf is None:
        return []

    suggestions = []
    for challenge_id in ctf["challenges"]:
        challenge = _challenge_repo.get_challenge_info(_id=challenge_id)
        if challenge is None:
            continue
        if unsolved_only and challenge["solved"]:
            continue

        display_name = f"{challenge['name']} ({challenge['category']})"
        if not current.strip() or current.lower() in display_name.lower():
            suggestions.append(Choice(name=display_name, value=challenge["name"]))

        if len(suggestions) == MAX_AUTOCOMPLETE_CHOICES:
            break
    return suggestions


class CTF(app_commands.Group):
    """Manage a CTF competition."""

    def __init__(self) -> None:
        super().__init__(name="ctf")
        self._chat_export_tasks = []

    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        # CheckFailure already handled by the check predicate with a user message
        if isinstance(error, app_commands.CheckFailure):
            return

        _log.exception(
            "Exception occurred due to `/%s %s`",
            interaction.command.parent.name,
            interaction.command.name,
            exc_info=error,
        )
        await send_response(interaction, "An exception has occurred")

    # =========================================================================
    # CTF Management Commands
    # =========================================================================

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    async def createctf(self, interaction: discord.Interaction, name: str) -> None:
        """Create a new CTF.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the CTF to create (case insensitive).
        """
        await interaction.response.defer()

        ctf = await interaction.client.create_ctf(name)
        if ctf:
            await send_response(
                interaction,
                f"{Emojis.SUCCESS} CTF `{name}` has been created.",
                ephemeral=False,
            )
            return

        await send_response(
            interaction,
            "Another CTF with similar name already exists, please choose another name",
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def renamectf(self, interaction: discord.Interaction, new_name: str) -> None:
        """Rename a previously created CTF.

        Args:
            interaction: The interaction that triggered this command.
            new_name: New CTF name (case insensitive).
        """
        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
        old_name = ctf["name"]

        category_channel = discord.utils.get(
            interaction.guild.categories, id=interaction.channel.category_id
        )

        _ctf_repo.set_name(ctf["_id"], new_name)
        await send_response(
            interaction,
            f"{Emojis.SUCCESS} CTF `{old_name}` has been renamed to `{new_name}`.",
            ephemeral=False,
        )

        await category_channel.edit(
            name=category_channel.name.replace(old_name, new_name)
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocomplete)
    async def archivectf(
        self,
        interaction: discord.Interaction,
        permissions: Optional[Permissions] = None,
        members: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """Archive a CTF by making its channels read-only by default.

        Args:
            interaction: The interaction that triggered this command.
            permissions: Whether channels should be read-only or writable
               as well (default: read only).
            members: A list of member or role mentions to be granted access into the
               private threads.
            name: CTF name (default: current channel's CTF).
        """
        if permissions is None:
            permissions = Permissions.RDONLY

        async def get_confirmation() -> bool:
            class Prompt(discord.ui.View):
                def __init__(view_self) -> None:
                    super().__init__(timeout=None)
                    view_self.add_item(
                        discord.ui.Button(style=discord.ButtonStyle.green, label="Yes")
                    )
                    view_self.add_item(
                        discord.ui.Button(style=discord.ButtonStyle.red, label="No")
                    )
                    view_self.children[0].callback = view_self.yes_callback
                    view_self.children[1].callback = view_self.no_callback

                async def yes_callback(
                    view_self, btn_interaction: discord.Interaction
                ) -> None:
                    await btn_interaction.response.edit_message(
                        content=f"{Emojis.ACTIVE} Starting CTF archival...",
                        view=None,
                    )
                    await self.archivectf.callback(
                        self,
                        interaction=btn_interaction,
                        permissions=permissions,
                        members=members or "",
                        name=name,
                    )

                async def no_callback(
                    view_self, btn_interaction: discord.Interaction
                ) -> None:
                    await btn_interaction.response.edit_message(
                        content="Aborting CTF archival.", view=None
                    )

            await send_response(
                interaction,
                (
                    "It appears that you forgot to set the `members` parameter, this "
                    "is important if you want to grant people access to private "
                    "threads that they weren't part of.\n"
                    f"{Emojis.WARNING} This action cannot be undone, "
                    "would you like to continue?"
                ),
                view=Prompt(),
            )

        if name is not None:
            ctf = _ctf_repo.get_ctf_info(name=name)
        else:
            ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        if not ctf:
            await send_response(
                interaction,
                (
                    (
                        "Run this command from within a CTF channel, or provide the "
                        "name of the CTF you wish to archive."
                    )
                    if name is None
                    else ErrorMessages.CTF_NOT_FOUND
                ),
            )
            return

        if ctf["archived"]:
            await send_response(interaction, "This CTF was already archived.")
            return

        if members is None:
            return await get_confirmation()

        if not interaction.response.is_done():
            await interaction.response.defer()

        category_channel = discord.utils.get(
            interaction.guild.categories, id=ctf["guild_category"]
        )
        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        challenges = [
            _challenge_repo.get_challenge_info(_id=challenge_id)
            for challenge_id in ctf["challenges"]
        ]

        challenges = sorted(
            challenges, key=lambda challenge: (challenge["category"], challenge["name"])
        )
        if challenges:
            name_field_width = (
                max(len(challenge["name"]) for challenge in challenges) + 10
            )

            head = (
                "```diff\n"
                f"  {'Challenge':<{name_field_width}}"
                f"{'Category':<30}{'Solved':<30}{'Blood'}\n\n{{}}"
                "```"
            )
            summaries = []
            summary = ""
            for challenge in challenges:
                content = (
                    f"{['-', '+'][challenge['solved']]} "
                    f"{challenge['name']:<{name_field_width}}"
                    f"{challenge['category']:<30}"
                    f"{['❌', '✔️'][challenge['solved']]:<30}"
                    f"{['', Emojis.FIRST_BLOOD][challenge['blooded']]}\n"
                )
                if len(head) - 2 + len(summary) + len(content) > MAX_CONTENT_SIZE:
                    summaries.append(summary)
                    summary = content
                else:
                    summary += content

            summaries.append(summary)

            scoreboard_channel = discord.utils.get(
                interaction.guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
            )
            for summary in summaries:
                await scoreboard_channel.send(head.format(summary))

        locked = permissions == Permissions.RDONLY
        for thread in interaction.guild.threads:
            if thread.parent is None or thread.category_id != ctf["guild_category"]:
                continue
            await thread.edit(locked=locked, invitable=True)

            if not members:
                continue

            message = await thread.send(content="Adding members...", silent=True)
            await message.edit(content=members)
            await message.delete()

        guild_members = [
            member
            async for member in interaction.guild.fetch_members(limit=None)
            if role in member.roles
        ]

        perm_rdwr = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        perm_rdonly = discord.PermissionOverwrite(
            read_messages=True, send_messages=False
        )

        ctf_general_channel = discord.utils.get(
            interaction.guild.text_channels,
            category_id=ctf["guild_category"],
            name=ChannelNames.GENERAL,
        )
        overwrites = {member: perm_rdwr for member in guild_members}
        overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(
            read_messages=False
        )
        await ctf_general_channel.edit(overwrites=overwrites)

        for member in guild_members:
            overwrites[member] = (
                perm_rdonly if permissions == Permissions.RDONLY else perm_rdwr
            )

        await category_channel.edit(
            name=f"{Emojis.LOCKED} {ctf['name']}", overwrites=overwrites
        )
        for ctf_channel in category_channel.channels:
            if ctf_channel.name == ChannelNames.GENERAL:
                continue
            await ctf_channel.edit(sync_permissions=True)

        if role:
            await role.delete()

        for challenge_id in ctf["challenges"]:
            _challenge_repo.delete(challenge_id)

        _ctf_repo.set_archived(ctf["_id"], archived=True, ended=True)

        msg = f"{Emojis.SUCCESS} CTF `{ctf['name']}` has been archived."
        if interaction.response.is_done():
            await interaction.edit_original_response(content=msg)
            return
        await send_response(interaction, msg, ephemeral=False)

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocomplete)
    async def deletectf(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ) -> None:
        """Delete a CTF.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the CTF to delete (default: CTF associated with the
                category channel from which the command was issued).
        """
        await interaction.response.defer()

        if name is not None:
            ctf = _ctf_repo.get_ctf_info(name=name)
        else:
            ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        if not ctf:
            await send_response(
                interaction,
                (
                    (
                        "Run this command from within a CTF channel, or provide the "
                        "name of the CTF you wish to delete."
                    )
                    if name is None
                    else ErrorMessages.CTF_NOT_FOUND
                ),
            )
            return

        category_channel = discord.utils.get(
            interaction.guild.categories, id=ctf["guild_category"]
        )
        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        for ctf_channel in category_channel.channels:
            await ctf_channel.delete()

        await category_channel.delete()

        if role:
            await role.delete()

        for challenge_id in ctf["challenges"]:
            _challenge_repo.delete(challenge_id)

        _ctf_repo.delete(ctf["_id"])

        if name and interaction.channel.category_id != category_channel.id:
            await send_response(
                interaction,
                f"{Emojis.SUCCESS} CTF `{ctf['name']}` has been deleted.",
                ephemeral=False,
            )

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    async def setprivacy(
        self,
        interaction: discord.Interaction,
        privacy: Privacy,
        name: Optional[str] = None,
    ) -> None:
        """Toggle a CTF privacy.

        Args:
            interaction: The interaction that triggered this command.
            privacy: The CTF privacy.
            name: Name of the CTF (default: CTF associated with the
                category channel from which the command was issued).
        """
        if name is not None:
            ctf = _ctf_repo.get_ctf_info(name=name)
        else:
            ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        if not ctf:
            await send_response(
                interaction,
                (
                    (
                        "Run this command from within a CTF channel, or provide the "
                        "name of the CTF for which you wish to change the privacy."
                    )
                    if name is None
                    else ErrorMessages.CTF_NOT_FOUND
                ),
            )
            return

        _ctf_repo.set_privacy(ctf["_id"], bool(privacy.value))
        await send_response(interaction, f"CTF privacy changed to `{privacy.name}`")

    @app_commands.checks.bot_has_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocomplete)
    async def addplayers(
        self, interaction: discord.Interaction, name: str, members: Optional[str] = None
    ) -> None:
        """Add members to a CTF.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the CTF to add people into (case insensitive).
            members: List of member mentions that you wish to add.
        """
        await interaction.response.defer()

        ctf = _ctf_repo.get_ctf_info(name=name)
        if ctf is None:
            await send_response(interaction, ErrorMessages.CTF_NOT_FOUND)
            return

        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])
        if role is None:
            await send_response(interaction, ErrorMessages.ROLE_DELETED)
            return

        ctf_general_channel = discord.utils.get(
            interaction.guild.text_channels,
            category_id=ctf["guild_category"],
            name=ChannelNames.GENERAL,
        )

        if members is None:
            for scheduled_event in interaction.guild.scheduled_events:
                if scheduled_event.name == ctf["name"]:
                    break
            else:
                await send_response(
                    interaction,
                    "No event matching the provided CTF name was found.",
                )
                return

            async for user in scheduled_event.users():
                member = await interaction.guild.fetch_member(user.id)
                await member.add_roles(role)
        else:
            for member in await parse_member_mentions(interaction, members):
                await member.add_roles(role)
                await ctf_general_channel.send(
                    f"{member.mention} was added by "
                    f"{interaction.user.mention} {Emojis.GUN}"
                )

        await send_response(
            interaction, f"{Emojis.SUCCESS} Added players to `{ctf['name']}`."
        )

    @app_commands.checks.bot_has_permissions(manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocomplete)
    async def join(self, interaction: discord.Interaction, name: str) -> None:
        """Join and ongoing CTF competition.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the CTF to join (case insensitive).
        """
        ctf = _ctf_repo.get_ctf_info(name=name)
        if ctf is None:
            await send_response(interaction, ErrorMessages.CTF_NOT_FOUND)
            return

        if ctf.get("private"):
            await send_response(
                interaction,
                "This CTF is private and requires invitation by an admin.",
            )
            return

        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])
        if role is None:
            await send_response(
                interaction,
                "CTF role was (accidentally?) deleted by an admin, aborting.",
            )
            return

        ctf_general_channel = discord.utils.get(
            interaction.guild.text_channels,
            category_id=ctf["guild_category"],
            name=ChannelNames.GENERAL,
        )
        await interaction.user.add_roles(role)
        await send_response(
            interaction, f"{Emojis.SUCCESS} Added to `{ctf['name']}`.", ephemeral=False
        )
        await ctf_general_channel.send(
            f"{interaction.user.mention} joined the battle {Emojis.SWORD}"
        )

    @app_commands.checks.bot_has_permissions(manage_roles=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def leave(self, interaction: discord.Interaction) -> None:
        """Leave the current CTF.

        Args:
            interaction: The interaction that triggered this command.
        """
        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
        if not ctf:
            return

        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        ctf_general_channel = discord.utils.get(
            interaction.guild.text_channels,
            category_id=ctf["guild_category"],
            name=ChannelNames.GENERAL,
        )
        await send_response(
            interaction, f"{Emojis.SUCCESS} Removed from `{ctf['name']}`."
        )
        await ctf_general_channel.send(
            f"{interaction.user.mention} abandoned the ship 😦"
        )

        _challenge_repo.remove_player_from_all(interaction.user.name)

        await interaction.user.remove_roles(role)

    # =========================================================================
    # Challenge Management Commands
    # =========================================================================

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def createchallenge(
        self,
        interaction: discord.Interaction,
        name: str,
        category: str,
    ) -> None:
        """Add a new challenge for the current CTF.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the challenge.
            category: Category of the challenge.
        """
        category = category.title().strip()

        if _challenge_repo.get_challenge_info(name=name, category=category):
            await send_response(interaction, ErrorMessages.CHALLENGE_ALREADY_EXISTS)
            return

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        if ctf["archived"]:
            await send_response(interaction, ErrorMessages.CTF_ARCHIVED)
            return

        category_channel = discord.utils.get(
            interaction.guild.categories, id=interaction.channel.category_id
        )

        text_channel = await get_challenge_category_channel(
            interaction.guild, category_channel, category
        )

        thread_name = sanitize_channel_name(name)
        challenge_thread = await text_channel.create_thread(
            name=f"{ThreadPrefixes.UNSOLVED}{thread_name}", invitable=False
        )

        challenge_oid = ObjectId()

        announcements_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["announcements"]
        )
        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        embed = discord.Embed(
            title=f"{Emojis.BELL} New challenge created!",
            description=(
                f"**Challenge name:** {name}\n"
                f"**Category:** {category}\n\n"
                f"Use `/ctf workon {name}` or the button to join.\n"
                f"{role.mention}"
            ),
            colour=EmbedColours.SUCCESS,
            timestamp=datetime.now(),
        )
        announcement = await announcements_channel.send(
            embed=embed, view=WorkonButton(oid=challenge_oid)
        )

        _challenge_repo.create(
            {
                "_id": challenge_oid,
                "id": None,
                "name": name,
                "category": category,
                "thread": challenge_thread.id,
                "solved": False,
                "blooded": False,
                "players": [],
                "announcement": announcement.id,
                "solve_time": None,
                "solve_announcement": None,
                "flag": None,
            }
        )

        _ctf_repo.add_challenge(ctf["_id"], challenge_oid)

        await send_response(
            interaction,
            f"{Emojis.SUCCESS} Challenge `{name}` has been created.",
            ephemeral=False,
        )
        await text_channel.edit(
            name=text_channel.name.replace(Emojis.SLEEPING, Emojis.ACTIVE).replace(
                Emojis.MAXED, Emojis.ACTIVE
            )
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def renamechallenge(
        self,
        interaction: discord.Interaction,
        new_name: str,
    ) -> None:
        """Rename a challenge.

        Args:
            interaction: The interaction that triggered this command.
            new_name: New challenge name.
        """
        challenge = _challenge_repo.get_challenge_info(thread=interaction.channel_id)
        if challenge is None:
            await send_response(interaction, ErrorMessages.NOT_IN_CHALLENGE_THREAD)
            return

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=interaction.channel_id
        )
        new_thread_name = sanitize_channel_name(new_name)
        prefix = ThreadPrefixes.get_prefix(challenge["solved"], challenge["blooded"])
        new_thread_name = f"{prefix}{new_thread_name}"

        _challenge_repo.set_name(challenge["_id"], new_name)
        await send_response(
            interaction, f"{Emojis.SUCCESS} Challenge renamed.", ephemeral=False
        )
        await challenge_thread.edit(name=new_thread_name)

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_all_challenges_autocomplete)
    @_in_ctf_channel()
    async def deletechallenge(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ) -> None:
        """Delete a challenge from the CTF.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the challenge to delete (default: current threads's
                challenge).
        """
        if name is None:
            challenge = _challenge_repo.get_challenge_info(
                thread=interaction.channel_id
            )
            if challenge is None:
                await send_response(
                    interaction,
                    "Run this command from within a challenge thread, "
                    "or provide the name of the challenge you wish to delete.",
                )
                return
        else:
            challenge = _challenge_repo.get_challenge_info(name=name)
            if challenge is None:
                await send_response(interaction, ErrorMessages.CHALLENGE_NOT_FOUND)
                return

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        _challenge_repo.delete(challenge["_id"])
        _ctf_repo.remove_challenge(ctf["_id"], challenge["_id"])

        announcements_channel = discord.utils.get(
            interaction.guild.text_channels,
            id=ctf["guild_channels"]["announcements"],
        )
        announcement = await announcements_channel.fetch_message(
            challenge["announcement"]
        )
        if announcement:
            await announcement.delete()

        await send_response(
            interaction,
            f"{Emojis.SUCCESS} Challenge `{challenge['name']}` has been deleted.",
            ephemeral=False,
        )

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )
        await challenge_thread.delete()

        text_channel = challenge_thread.parent
        if len(text_channel.threads) == 0:
            await text_channel.edit(
                name=text_channel.name.replace(Emojis.ACTIVE, Emojis.SLEEPING).replace(
                    Emojis.MAXED, Emojis.SLEEPING
                )
            )

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_challenge_autocomplete)
    @_in_ctf_channel()
    async def workon(self, interaction: discord.Interaction, name: str) -> None:
        """Start working on a challenge and join its thread.

        Args:
            interaction: The interaction that triggered this command.
            name: Challenge name (case insensitive).
        """
        challenge = _challenge_repo.get_challenge_info(name=name)
        if challenge is None:
            await send_response(interaction, ErrorMessages.CHALLENGE_NOT_FOUND)
            return

        if interaction.user.name in challenge["players"]:
            await send_response(
                interaction, "You're already working on this challenge."
            )
            return

        if challenge["solved"]:
            await send_response(
                interaction, "You can't work on a challenge that has been solved."
            )
            return

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )
        await add_challenge_worker(challenge_thread, challenge, interaction.user)

        await send_response(
            interaction,
            f"{Emojis.SUCCESS} Added to the `{challenge['name']}` challenge.",
            ephemeral=False,
        )
        await challenge_thread.send(
            f"{interaction.user.mention} wants to collaborate {Emojis.HANDSHAKE}"
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_challenge_autocomplete)
    @_in_ctf_channel()
    async def unworkon(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ) -> None:
        """Stop working on a challenge and leave its thread.

        Args:
            interaction: The interaction that triggered this command.
            name: Challenge name (case insensitive).
        """
        if name is None:
            challenge = _challenge_repo.get_challenge_info(
                thread=interaction.channel_id
            )
            if challenge is None:
                await send_response(
                    interaction,
                    "Run this command from within a challenge thread, "
                    "or provide the name of the challenge you wish to stop "
                    "working on.",
                )
                return
        else:
            challenge = _challenge_repo.get_challenge_info(name=name)
            if challenge is None:
                await send_response(interaction, ErrorMessages.CHALLENGE_NOT_FOUND)
                return

        if interaction.user.name not in challenge["players"]:
            await send_response(
                interaction, "You're not working on this challenge in the first place."
            )
            return

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )
        await remove_challenge_worker(challenge_thread, challenge, interaction.user)
        await challenge_thread.send(
            f"{interaction.user.name} left you alone, what a chicken! {Emojis.CHICKEN}"
        )

        await send_response(
            interaction,
            f"{Emojis.SUCCESS} Removed from the `{challenge['name']}` challenge.",
        )

    @app_commands.command()
    @app_commands.autocomplete(name=_all_challenges_autocomplete)
    @_in_ctf_channel()
    async def showsolvers(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ) -> None:
        """Show teams that solved a challenge.

        Args:
            interaction: The interaction that triggered this command.
            name: Challenge name (default: current thread's challenge).
        """
        await interaction.response.defer()

        # Get challenge from thread or by name
        if name is None:
            challenge = _challenge_repo.get_challenge_info(
                thread=interaction.channel_id
            )
            if challenge is None:
                await send_response(
                    interaction,
                    "Run this command from within a challenge thread, "
                    "or provide the name of the challenge.",
                )
                return
        else:
            challenge = _challenge_repo.get_challenge_info(name=name)
            if challenge is None:
                await send_response(interaction, ErrorMessages.CHALLENGE_NOT_FOUND)
                return

        # Check if challenge has a platform ID
        if challenge.get("id") is None:
            await send_response(
                interaction,
                "This challenge was not pulled from a platform, "
                "solver information is unavailable.",
            )
            return

        # Get CTF and credentials
        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
        credentials = ctf.get("credentials", {})
        if not credentials.get("url"):
            await send_response(interaction, ErrorMessages.NO_CREDENTIALS)
            return

        # Match and login to platform
        ctx = PlatformCTX.from_credentials(credentials)
        platform = await match_platform(ctx)
        if platform is None:
            await send_response(interaction, "Could not identify the CTF platform.")
            return

        if not await ctx.login(platform.impl.login):
            await send_response(
                interaction, "Could not authenticate with the platform."
            )
            return

        me = await platform.impl.get_me(ctx)
        our_team_name = me.name if me is not None else TEAM_NAME

        # Pull solvers
        solvers = []
        async for solver in platform.impl.pull_challenge_solvers(
            ctx, challenge_id=str(challenge["id"])
        ):
            solvers.append(solver)

        if not solvers:
            await send_response(
                interaction,
                f"No solvers for `{challenge['name']}` yet.",
                ephemeral=False,
            )
            return

        # Build table like scoreboard
        name_width = max(len(solver.team.name) for solver in solvers) + 5
        header = f"  {'Rank':<8}{'Team':<{name_width}}{'Solved'}\n"

        lines = []
        for rank, solver in enumerate(solvers, start=1):
            is_us = our_team_name and solver.team.name == our_team_name
            prefix = "+" if is_us else "-"

            solved_at = solver.solved_at.strftime("%Y-%m-%d %H:%M UTC")
            line = f"{prefix} {rank:<8}{solver.team.name:<{name_width}}{solved_at}\n"
            lines.append(line)

        message = (
            f"**Solvers for {challenge['name']}**\n"
            "```diff\n"
            f"{header}"
            f"{''.join(lines)}"
            "```"
        )

        await send_response(interaction, message, ephemeral=False)

    # =========================================================================
    # Submission Commands
    # =========================================================================

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def solve(
        self, interaction: discord.Interaction, members: Optional[str] = None
    ) -> None:
        """Mark the challenge as solved.

        Args:
            interaction: The interaction that triggered this command.
            members: List of member mentions who contributed in solving the challenge.
        """
        await interaction.response.defer()

        challenge = _challenge_repo.get_challenge_info(thread=interaction.channel_id)
        if challenge is None:
            await send_error(interaction, ErrorMessages.NOT_IN_CHALLENGE_THREAD)
            return

        if challenge["solved"]:
            await send_error(interaction, ErrorMessages.CHALLENGE_ALREADY_SOLVED)
            return

        solve_time = int(datetime.now().timestamp())
        solvers = await parse_challenge_solvers(interaction, challenge, members)

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
        solves_channel = interaction.client.get_channel(ctf["guild_channels"]["solves"])
        embed = discord.Embed(
            title=f"{Emojis.CELEBRATION} Challenge solved!",
            description=(
                f"**{', '.join(solvers)}** just solved "
                f"**{challenge['name']}** from the "
                f"**{challenge['category']}** category!"
            ),
            colour=EmbedColours.SUCCESS,
            timestamp=datetime.now(),
        ).set_thumbnail(url=interaction.user.display_avatar.url)
        solve_announcement = await solves_channel.send(embed=embed)

        _challenge_repo.update_solve_details(
            challenge_id=challenge["_id"],
            solved=True,
            blooded=False,
            solve_time=solve_time,
            solve_announcement=solve_announcement.id,
            players=challenge["players"],
        )

        announcements_channel = discord.utils.get(
            interaction.guild.text_channels,
            id=ctf["guild_channels"]["announcements"],
        )
        announcement = await announcements_channel.fetch_message(
            challenge["announcement"]
        )
        await announcement.edit(view=WorkonButton(oid=challenge["_id"], disabled=True))

        await send_response(
            interaction, f"{Emojis.SUCCESS} Challenge solved.", ephemeral=False
        )
        await send_response(
            interaction,
            f"{Emojis.INFO} Use `/ctf submit` instead to track first bloods.",
        )

        await interaction.channel.edit(
            name=interaction.channel.name.replace(
                ThreadPrefixes.UNSOLVED, ThreadPrefixes.SOLVED
            )
        )

        await mark_if_maxed(interaction.channel.parent, challenge["category"])

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def unsolve(self, interaction: discord.Interaction) -> None:
        """Mark the challenge as not solved.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.defer()

        challenge = _challenge_repo.get_challenge_info(thread=interaction.channel_id)
        if challenge is None:
            await send_error(interaction, ErrorMessages.NOT_IN_CHALLENGE_THREAD)
            return

        if not challenge["solved"]:
            await send_response(
                interaction, "This challenge is already marked as not solved."
            )
            return

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
        solves_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["solves"]
        )
        announcement = await solves_channel.fetch_message(
            challenge["solve_announcement"]
        )
        if announcement:
            await announcement.delete()

        _challenge_repo.update_solve_details(
            challenge_id=challenge["_id"],
            solved=False,
            blooded=False,
            solve_time=None,
            solve_announcement=None,
            players=challenge["players"],
        )

        announcements_channel = discord.utils.get(
            interaction.guild.text_channels,
            id=ctf["guild_channels"]["announcements"],
        )
        announcement = await announcements_channel.fetch_message(
            challenge["announcement"]
        )
        await announcement.edit(view=WorkonButton(oid=challenge["_id"]))

        await send_response(
            interaction, f"{Emojis.SUCCESS} Challenge unsolved.", ephemeral=False
        )

        # Replace both solved and first blood prefixes with unsolved
        new_name = interaction.channel.name
        new_name = new_name.replace(ThreadPrefixes.SOLVED, ThreadPrefixes.UNSOLVED)
        new_name = new_name.replace(ThreadPrefixes.FIRST_BLOOD, ThreadPrefixes.UNSOLVED)
        await interaction.channel.edit(name=new_name)

        text_channel = interaction.channel.parent
        if text_channel.name.startswith(Emojis.MAXED):
            await text_channel.edit(
                name=text_channel.name.replace(Emojis.MAXED, Emojis.ACTIVE)
            )

    @app_commands.command()
    @_in_ctf_channel()
    async def submit(
        self, interaction: discord.Interaction, members: Optional[str] = None
    ) -> None:
        """Submit a flag to the platform.

        Args:
            interaction: The interaction that triggered this command.
            members: List of member mentions who contributed in solving the challenge.
        """
        await interaction.response.send_modal(FlagSubmissionForm(members=members))

    # =========================================================================
    # Status and Information Commands
    # =========================================================================

    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocomplete)
    async def status(
        self,
        interaction: discord.Interaction,
        name: str = None,
        mode: Optional[CTFStatusMode] = CTFStatusMode.active,
    ) -> None:
        """Display CTF status.

        Args:
            interaction: The interaction that triggered this command.
            name: CTF name (default: current channel's CTF).
            mode: Whether to display all challenges or only those not
                solved (default: active).
        """
        await interaction.response.defer()

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        if ctf is None and name is None:
            ctfs = _ctf_repo.find_active()
        elif name is None:
            ctfs = [ctf]
        else:
            ctfs = _ctf_repo.get_ctf_info(name=name, archived=False, ended=False)
            if ctfs is None:
                await send_response(interaction, ErrorMessages.CTF_NOT_FOUND)
                return
            ctfs = [ctfs]

        no_running_ctfs = True
        for ctf in ctfs:
            no_running_ctfs = False
            if ctf["guild_category"] != interaction.channel.category_id:
                embed = discord.Embed(
                    title=f"{ctf['name']} status",
                    colour=EmbedColours.INFO,
                    description=(
                        "You must run the command in one of the CTF's channels to see "
                        "its details."
                    ),
                )
                await interaction.followup.send(embed=embed)
                continue

            challenges = ctf["challenges"]
            if not challenges:
                embed = discord.Embed(
                    title=f"{ctf['name']} status",
                    description="No challenges added yet.",
                    colour=EmbedColours.INFO,
                )
                await interaction.followup.send(embed=embed)
                return

            embed = None
            num_fields = 0
            for idx, challenge_id in enumerate(challenges):
                if num_fields % MAX_EMBED_FIELDS == 0:
                    if num_fields != 0:
                        await interaction.followup.send(embed=embed)
                        embed = None

                    if embed is None:
                        embed = discord.Embed(
                            title=f"{ctf['name']} status",
                            colour=EmbedColours.INFO,
                        )

                challenge = _challenge_repo.get_challenge_info(_id=challenge_id)
                if challenge["solved"] and mode == CTFStatusMode.all:
                    icon = Emojis.FIRST_BLOOD if challenge["blooded"] else Emojis.SOLVED
                    solve_time = datetime.utcfromtimestamp(
                        challenge["solve_time"]
                    ).strftime(DATE_FORMAT)
                    embed.add_field(
                        name=f"{icon} {challenge['name']} ({challenge['category']})",
                        value=(
                            "```diff\n"
                            f"+ Solver{['', 's'][len(challenge['players']) > 1]}:"
                            f" {', '.join(challenge['players']).strip()}\n"
                            f"+ Date: {solve_time}\n"
                            "```"
                        ),
                        inline=False,
                    )
                    num_fields += 1
                elif not challenge["solved"]:
                    workers = (
                        "```diff\n- No workers.\n```"
                        if len(challenge["players"]) == 0
                        else (
                            "```fix\n"
                            f"! Worker{['', 's'][len(challenge['players']) > 1]}:"
                            f" {', '.join(challenge['players']).strip()}\n"
                            "```"
                        )
                    )
                    embed.add_field(
                        name=(
                            f"{Emojis.UNSOLVED} {idx + 1:2} - "
                            f"{challenge['name']} ({challenge['category']})"
                        ),
                        value=workers,
                        inline=False,
                    )
                    num_fields += 1

            await interaction.followup.send(embed=embed)

        if no_running_ctfs:
            if name is None:
                await send_response(interaction, "No running CTFs.")
            else:
                await send_response(interaction, ErrorMessages.CTF_NOT_FOUND)

    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def addcreds(self, interaction: discord.Interaction, url: str) -> None:
        """Add credentials for the current CTF.

        Args:
            interaction: The interaction that triggered this command.
            url: Base URL of the CTF platform.
        """
        ctx = PlatformCTX(base_url=strip_url_components(url.strip()))
        try:
            platform = await match_platform(ctx)
        except InvalidURL:
            await send_response(interaction, "The provided URL was invalid.")
            return
        except ClientError:
            await send_response(
                interaction,
                "Could not communicate with the CTF platform, please try again.",
            )
            return

        if platform is None:
            await send_response(
                interaction,
                f"{Emojis.ERROR} Unsupported platform. Supported: CTFd, rCTF.",
            )
            return

        modal = await create_credentials_modal_for_platform(url, platform, interaction)
        if modal is not None:
            await interaction.response.send_modal(modal)

    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def showcreds(self, interaction: discord.Interaction) -> None:
        """Show credentials for the current CTF.

        Args:
            interaction: The interaction that triggered this command.
        """
        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)
        if (message := ctf["credentials"].get("_message")) is None:
            await send_response(interaction, ErrorMessages.NO_CREDENTIALS)
            return
        await send_response(interaction, message, ephemeral=False)

    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def pull(self, interaction: discord.Interaction) -> None:
        """Pull challenges from the platform.

        Args:
            interaction: The interaction that triggered this command.
        """
        if interaction.client.challenge_puller_is_running:
            await send_response(interaction, "Challenge puller is already running.")
            return
        interaction.client.challenge_puller.restart()
        await send_response(
            interaction, f"{Emojis.SUCCESS} Started challenge puller.", ephemeral=False
        )

    @app_commands.command()
    @_in_ctf_channel()
    async def scoreboard(self, interaction: discord.Interaction) -> None:
        """Display scoreboard for the current CTF.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.defer()

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        await _scoreboard_service.send_scoreboard(ctf, interaction=interaction)

    @app_commands.command()
    @_in_ctf_channel()
    async def remaining(self, interaction: discord.Interaction) -> None:
        """Show remaining time for the CTF.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.defer()

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        for scheduled_event in interaction.guild.scheduled_events:
            if scheduled_event.name == ctf["name"]:
                break
        else:
            await send_response(
                interaction,
                f"{Emojis.ENDED} This CTF has ended or we don't know its end time.",
                ephemeral=False,
            )
            return

        end_ts = int(scheduled_event.end_time.timestamp())
        await send_response(
            interaction,
            f"{Emojis.PENDING} This CTF ends <t:{end_ts}:R>.",
            ephemeral=False,
        )

    @app_commands.command()
    @_in_ctf_channel()
    async def register(
        self,
        interaction: discord.Interaction,
        url: str,
    ) -> None:
        """Register a team account in the platform.

        Args:
            interaction: The interaction that triggered this command.
            url: Platform base url.
        """
        url = strip_url_components(url.strip())
        ctx: PlatformCTX = PlatformCTX(base_url=url)
        try:
            platform = await match_platform(ctx)
        except InvalidURL:
            await send_response(interaction, "The provided URL was invalid.")
            return
        except ClientError:
            await send_response(
                interaction,
                "Could not communicate with the CTF platform, please try again.",
            )
            return

        form = await create_credentials_modal_for_platform(
            url=url, platform=platform, interaction=interaction, is_registration=True
        )

        if not form:
            await send_response(
                interaction,
                "Invalid URL set for this CTF, or platform isn't supported.",
            )
            return

        await interaction.response.send_modal(form)

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    async def exportchat(self, interaction: discord.Interaction) -> None:
        """Export CTF chat logs to a static site.

        Args:
            interaction: The interaction that triggered this command.
        """

        async def _handle_process(process: asyncio.subprocess.Process):
            _, _ = await process.communicate()
            channel, _, _ = self._chat_export_tasks.pop(0)
            message = (
                "Chat export task finished successfully, "
                f"{len(self._chat_export_tasks)} items remaining in the queue."
            )
            try:
                await channel.send(content=message)
            except discord.errors.HTTPException as err:
                _log.error("Failed to send message: %s", err)

            _log.info(message)
            if len(self._chat_export_tasks) == 0:
                return

            _, tmp, output_dirname = self._chat_export_tasks[0]
            asyncio.create_task(
                _handle_process(
                    await asyncio.create_subprocess_exec(
                        "chat_exporter",
                        tmp,
                        output_dirname,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                )
            )

        await interaction.response.defer()

        guild_category = interaction.channel.category
        exportable = set()
        for channel in guild_category.text_channels:
            exportable.add(channel.id)

            for thread in channel.threads:
                exportable.add(thread.id)

            for private in (True, False):
                async for thread in channel.archived_threads(
                    private=private, limit=None
                ):
                    exportable.add(thread.id)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("\n".join(map(str, exportable)))
            tmp = f.name

        output_dirname = (
            f"[{guild_category.id}] {guild_category.name.replace('/', '_')}"
        )

        self._chat_export_tasks.append((interaction.channel, tmp, output_dirname))
        if len(self._chat_export_tasks) == 1:
            asyncio.create_task(
                _handle_process(
                    await asyncio.create_subprocess_exec(
                        "chat_exporter",
                        tmp,
                        output_dirname,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                )
            )

        await send_response(
            interaction,
            "Export task started, chat logs will be available shortly.",
            ephemeral=False,
            silent=True,
        )


__all__ = ["CTF"]
