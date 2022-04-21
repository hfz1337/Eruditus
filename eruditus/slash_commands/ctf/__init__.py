import re

from typing import Optional, List
from datetime import datetime, timezone

import discord
from discord import HTTPException, app_commands
from discord.app_commands import Choice

from lib.util import sanitize_channel_name
from lib.ctfd import pull_challenges, get_scoreboard

from lib.types import ArchiveMode, CTFStatusMode, NoteFormat, NoteType
from forms.flag import FlagSubmissionForm
from buttons.workon import WorkonButton
from config import (
    CHALLENGE_COLLECTION,
    CTF_COLLECTION,
    DATE_FORMAT,
    DBNAME,
    MAX_CONTENT_SIZE,
    MONGO,
)


class CTF(app_commands.Group):
    """Manage a CTF competition."""

    def __init__(self) -> None:
        super().__init__(name="ctf")

    def _in_ctf_channel() -> bool:
        """Wrapper function to check if a command was issued from a CTF channel."""

        async def predicate(interaction: discord.Interaction) -> bool:
            if MONGO[DBNAME][CTF_COLLECTION].find_one(
                {"guild_category": interaction.channel.category_id}
            ):
                return True

            await interaction.response.send_message(
                "You must be in a CTF channel to use this command.", ephemeral=True
            )
            return False

        return app_commands.check(predicate)

    async def _ctf_autocompletion_func(
        self, interaction: discord.Interaction, current: str
    ) -> List[Choice[str]]:
        """Autocomplete CTF name.
        This function is inefficient, might improve it later.

        Args:
            interaction: The interaction that triggered this command.
            current: The CTF name typed so far.

        Returns:
            A list of suggestions.
        """
        suggestions = []
        for ctf in MONGO[DBNAME][CTF_COLLECTION].find({"archived": False}):
            if current.lower() in ctf["name"].lower():
                suggestions.append(Choice(name=ctf["name"], value=ctf["name"]))
            if len(suggestions) == 25:
                break
        return suggestions

    async def _challenge_autocompletion_func(
        self, interaction: discord.Interaction, current: str
    ) -> List[Choice[str]]:
        """Autocomplete challenge name.
        This function is inefficient, might improve it later.

        Args:
            interaction: The interaction that triggered this command.
            current: The challenge name typed so far.

        Returns:
            A list of suggestions.
        """
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        if ctf is None:
            return []

        suggestions = []
        for challenge_id in ctf["challenges"]:
            challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(challenge_id)
            if challenge is None or challenge["solved"]:
                continue

            display_name = f"{challenge['name']} ({challenge['category']})"
            if current.lower() in display_name.lower():
                suggestions.append(Choice(name=display_name, value=challenge["name"]))
            if len(suggestions) == 25:
                break
        return suggestions

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
        if ctf is None:
            await interaction.followup.send(
                "Another CTF with similar name already exists, please choose "
                "another name.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"✅ CTF `{name}` has been created.")

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
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        old_name = ctf["name"]
        ctf["name"] = new_name

        category_channel = discord.utils.get(
            interaction.guild.categories, id=interaction.channel.category_id
        )

        # Rename category channel for the CTF.
        await category_channel.edit(
            name=category_channel.name.replace(old_name, new_name)
        )

        # Update CTF name in the database.
        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]}, {"$set": {"name": ctf["name"]}}
        )
        await interaction.response.send_message(
            f"✅ CTF `{old_name}` has been renamed to `{new_name}`."
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocompletion_func)
    async def archivectf(
        self,
        interaction: discord.Interaction,
        mode: Optional[ArchiveMode] = ArchiveMode.minimal,
        name: Optional[str] = None,
    ):
        """Archive a CTF by making its channels read-only.

        Args:
            interaction: The interaction that triggered this command.
            mode: Whether to archive all channels, or the important ones
               only (default: minimal).
            name: CTF name (default: current channel's CTF).
        """
        await interaction.response.defer()

        if name is None:
            ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
                {"guild_category": interaction.channel.category_id}
            )
            if ctf is None:
                await interaction.followup.send(
                    (
                        "Run this command from within a CTF channel, or provide the "
                        "name of the CTF you wish to delete."
                    ),
                    ephemeral=True,
                )
                return
        else:
            ctf = MONGO[DBNAME][f"{CTF_COLLECTION}"].find_one({"name": name})
            if ctf is None:
                await interaction.followup.send("No such CTF.", ephemeral=True)
                return

        category_channel = discord.utils.get(
            interaction.guild.categories, id=ctf["guild_category"]
        )
        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        # Get all challenges for the CTF.
        challenges = [
            MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(challenge_id)
            for challenge_id in ctf["challenges"]
        ]

        # Sort by category, then by name.
        challenges = sorted(
            challenges, key=lambda challenge: (challenge["category"], challenge["name"])
        )
        name_field_width = max(len(challenge["name"]) for challenge in challenges) + 10

        # Post final scoreboard and challenge solves summary in the scoreboard
        # channel.
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
                f"{['', '🩸'][challenge['blooded']]}\n"
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

        # Delete unimportant channels if we are in minimal mode.
        if mode == ArchiveMode.minimal:
            for ctf_channel in category_channel.channels:
                if (
                    ctf_channel.id != ctf["guild_channels"]["notes"]
                    and ctf_channel.id != ctf["guild_channels"]["solves"]
                    and ctf_channel.id != ctf["guild_channels"]["scoreboard"]
                ):
                    await ctf_channel.delete()

        # Make the channels world readable.
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                send_messages=False
            )
        }
        await category_channel.edit(
            name=f"🔒 {ctf['name']}",
            overwrites=overwrites,
        )
        for ctf_channel in category_channel.channels:
            await ctf_channel.edit(sync_permissions=True)

        # Delete the CTF role.
        if role:
            await role.delete()

        # Delete all challenges for that CTF from the database.
        for challenge_id in ctf["challenges"]:
            MONGO[DBNAME][CHALLENGE_COLLECTION].delete_one({"_id": challenge_id})

        # Update status of the CTF.
        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]}, {"$set": {"archived": True}}
        )

        # Only send a followup message if the channel from which the command was issued
        # still exists, otherwise we will fail with a 404 not found.
        if interaction.channel in category_channel.text_channels:
            await interaction.followup.send(f"✅ CTF `{ctf['name']}` has been archived.")

    @app_commands.checks.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.checks.has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocompletion_func)
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

        if name is None:
            ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
                {"guild_category": interaction.channel.category_id}
            )
            if ctf is None:
                await interaction.followup.send(
                    (
                        "Run this command from within a CTF channel, or provide the "
                        "name of the CTF you wish to delete."
                    ),
                    ephemeral=True,
                )
                return
        else:
            ctf = MONGO[DBNAME][f"{CTF_COLLECTION}"].find_one({"name": name})
            if ctf is None:
                await interaction.followup.send("No such CTF.", ephemeral=True)
                return

        category_channel = discord.utils.get(
            interaction.guild.categories, id=ctf["guild_category"]
        )
        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        # Delete all channels.
        for ctf_channel in category_channel.channels:
            await ctf_channel.delete()

        # Delete the category channel.
        await category_channel.delete()

        # Delete the CTF role.
        if role:
            await role.delete()

        # Delete all challenges for that CTF from the database.
        for challenge_id in ctf["challenges"]:
            MONGO[DBNAME][CHALLENGE_COLLECTION].delete_one({"_id": challenge_id})

        # Delete the CTF from the database.
        MONGO[DBNAME][CTF_COLLECTION].delete_one({"_id": ctf["_id"]})

        # Only send a followup message if the channel from which the command was issued
        # still exists, otherwise we will fail with a 404 not found.
        if name and interaction.channel.category_id != category_channel.id:
            await interaction.followup.send(f"✅ CTF `{ctf['name']}` has been deleted.")

    @app_commands.checks.bot_has_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocompletion_func)
    async def addplayers(
        self, interaction: discord.Interaction, name: str, members: str
    ) -> None:
        """Add members to a CTF.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the CTF to add people into (case insensitive).
            members: List of member mentions that you wish to add.
        """
        await interaction.response.defer()

        ctf = MONGO[DBNAME][f"{CTF_COLLECTION}"].find_one({"name": name})
        if ctf is None:
            await interaction.followup.send("No such CTF.", ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])
        if role is None:
            await interaction.followup.send(
                "CTF role was (accidently?) deleted by an admin, aborting.",
                ephemeral=True,
            )
            return

        ctf_general_channel = discord.utils.get(
            interaction.guild.text_channels,
            category_id=ctf["guild_category"],
            name="general",
        )

        for member_id in re.findall(r"<@!?([0-9]{15,20})>", members):
            member = await interaction.guild.fetch_member(int(member_id))
            if member is None:
                continue
            await member.add_roles(role)
            await ctf_general_channel.send(
                f"{member.mention} was added by {interaction.user.mention} 🔫"
            )

        await interaction.followup.send(f"✅ Added players to `{ctf['name']}`.")

    @app_commands.checks.bot_has_permissions(manage_roles=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocompletion_func)
    async def join(self, interaction: discord.Interaction, name: str) -> None:
        """Join and ongoing CTF competition.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the CTF to join (case insensitive).
        """
        ctf = MONGO[DBNAME][f"{CTF_COLLECTION}"].find_one({"name": name})
        if ctf is None:
            await interaction.response.send_message("No such CTF.", ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])
        if role is None:
            await interaction.response.send_message(
                "CTF role was (accidently?) deleted by an admin, aborting.",
                ephemeral=True,
            )
            return

        ctf_general_channel = discord.utils.get(
            interaction.guild.text_channels,
            category_id=ctf["guild_category"],
            name="general",
        )
        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"✅ Added to `{ctf['name']}`.")
        await ctf_general_channel.send(
            f"{interaction.user.mention} joined the battle ⚔️"
        )

    @app_commands.checks.bot_has_permissions(manage_roles=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def leave(self, interaction: discord.Interaction) -> None:
        """Leave the current CTF.

        Args:
            interaction: The interaction that triggered this command.
        """
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        if not ctf:
            return

        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        # Announce that the user left the CTF.
        ctf_general_channel = discord.utils.get(
            interaction.guild.text_channels,
            category_id=ctf["guild_category"],
            name="general",
        )
        await interaction.response.send_message(
            f"✅ Removed from `{ctf['name']}`.", ephemeral=True
        )
        await ctf_general_channel.send(
            f"{interaction.user.mention} abandonned the ship :frowning:"
        )

        # Remove role and permissions.
        for challenge in MONGO[DBNAME][CHALLENGE_COLLECTION].find():
            if interaction.user.name in challenge["players"]:
                challenge_channel = discord.utils.get(
                    interaction.guild.text_channels, id=challenge["channel"]
                )
                await challenge_channel.set_permissions(
                    interaction.user, overwrite=None
                )
        await interaction.user.remove_roles(role)

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
        # Avoid having duplicate categories when people mix up upper/lower case
        # or add unnecessary spaces at the beginning or the end.
        category = category.title().strip()

        # Check if challenge already exists.
        if MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
            {
                "name": re.compile(f"^{name.strip()}$", re.IGNORECASE),
                "category": re.compile(f"^{category}$", re.IGNORECASE),
            }
        ):
            await interaction.response.send_message(
                "This challenge already exists.", ephemeral=True
            )
            return

        # Create a channel for the challenge and set its permissions.
        category_channel = discord.utils.get(
            interaction.guild.categories, id=interaction.channel.category_id
        )
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            )
        }
        channel_name = sanitize_channel_name(f"{category}-{name}")
        challenge_channel = await interaction.guild.create_text_channel(
            name=f"❌-{channel_name}",
            category=category_channel,
            overwrites=overwrites,
        )

        # Add challenge to the database.
        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].insert_one(
            {
                "id": None,
                "name": name,
                "category": category,
                "channel": challenge_channel.id,
                "solved": False,
                "blooded": False,
                "players": [],
                "solve_time": None,
                "solve_announcement": None,
            }
        )

        # Add reference to the newly created challenge.
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctf["challenges"].append(challenge.inserted_id)
        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]}, {"$set": {"challenges": ctf["challenges"]}}
        )

        # Announce that the challenge was added.
        announcements_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["announcements"]
        )
        role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

        embed = discord.Embed(
            title="🔔 New challenge created!",
            description=(
                f"**Challenge name:** {name}\n"
                f"**Category:** {category}\n\n"
                f"Use `/ctf workon {challenge['name']}` or the button to join.\n"
                f"{role.mention}"
            ),
            colour=discord.Colour.dark_gold(),
        ).set_footer(text=datetime.strftime(datetime.now(tz=timezone.utc), DATE_FORMAT))
        await announcements_channel.send(
            embed=embed, view=WorkonButton(name=challenge["name"])
        )
        await interaction.response.send_message(
            f"✅ Challenge `{name}` has been created."
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def renamechallenge(
        self,
        interaction: discord.Interaction,
        new_name: str,
        new_category: Optional[str] = None,
    ) -> None:
        """Rename a challenge.

        Args:
            interaction: The interaction that triggered this command.
            new_name: New challenge name.
            new_category: New challenge category.
        """
        # Avoid having duplicate categories when people mix up upper/lower case
        # or add unnecessary spaces at the beginning or the end.
        new_category = new_category.title().strip() if new_category else None

        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
            {"channel": interaction.channel_id}
        )

        if challenge is None:
            await interaction.response.send_message(
                "Run this command from within a challenge channel.",
                ephemeral=True,
            )
            return

        challenge["name"] = new_name
        challenge["category"] = new_category or challenge["category"]
        new_channel_name = sanitize_channel_name(
            f"{challenge['category']}-{challenge['name']}"
        )

        challenge_channel = discord.utils.get(
            interaction.guild.text_channels, id=interaction.channel_id
        )
        if challenge["blooded"]:
            await challenge_channel.edit(name=f"🩸-{new_channel_name}")
        if challenge["solved"]:
            await challenge_channel.edit(name=f"✅-{new_channel_name}")
        else:
            await challenge_channel.edit(name=f"❌-{new_channel_name}")

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"name": challenge["name"], "category": challenge["category"]}},
        )
        await interaction.response.send_message("✅ Challenge renamed.")

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_challenge_autocompletion_func)
    @_in_ctf_channel()
    async def deletechallenge(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ) -> None:
        """Delete a challenge from the CTF.

        Args:
            interaction: The interaction that triggered this command.
            name: Name of the challenge to delete (default: current channel's
                challenge).
        """
        if name is None:
            challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
                {"channel": interaction.channel_id}
            )
            if challenge is None:
                await interaction.response.send_message(
                    (
                        "Run this command from within a challenge channel, "
                        "or provide the name of the challenge you wish to delete."
                    ),
                    ephemeral=True,
                )
                return
        else:
            challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one({"name": name})
            if challenge is None:
                await interaction.response.send_message(
                    "No such challenge.", ephemeral=True
                )
                return

        # Delete challenge from the database.
        MONGO[DBNAME][CHALLENGE_COLLECTION].delete_one(challenge)

        # Get CTF to which the challenge is associated.
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )

        # Delete channel associated with the challenge.
        challenge_channel = discord.utils.get(
            interaction.guild.text_channels, id=challenge["channel"]
        )
        await challenge_channel.delete()

        # Delete reference to that challenge from the CTF.
        ctf["challenges"].remove(challenge["_id"])
        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]}, {"$set": {"challenges": ctf["challenges"]}}
        )

        await interaction.response.send_message(
            f"✅ Challenge `{challenge['name']}` has been deleted."
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def solve(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Mark the challenge as solved by you and other collaborators in
        the channel.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.defer()

        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
            {"channel": interaction.channel_id}
        )
        if challenge is None:
            # If we didn't find any challenge that corresponds to the channel from which
            # the command was run, then we're probably in the wrong channel.
            await interaction.followup.send(
                "You may only run this command in the channel associated to the "
                "challenge.",
                ephemeral=True,
            )
            return

        # If the challenged was already solved.
        if challenge["solved"]:
            await interaction.followup.send(
                "This challenge was already solved.", ephemeral=True
            )
            return

        challenge["solved"] = True
        challenge["solve_time"] = datetime.now(tz=timezone.utc).strftime(DATE_FORMAT)

        try:
            await interaction.channel.edit(
                name=interaction.channel.name.replace("❌", "✅")
            )
        except HTTPException:
            # We've exceeded the 2 channel edit per 10 min set by Discord.
            # This should only happen during testing, or when the users are trolling
            # by spamming solve and unsolve.
            pass

        # Add the user who triggered this interaction to the list of players, useful
        # in case the one who triggered the interaction is an admin.
        if interaction.user.name not in challenge["players"]:
            challenge["players"].append(interaction.user.name)

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        solves_channel = interaction.client.get_channel(ctf["guild_channels"]["solves"])
        embed = (
            discord.Embed(
                title="🎉 Challenge solved!",
                description=(
                    f"**{', '.join(challenge['players'])}** just solved "
                    f"**{challenge['name']}** from the "
                    f"**{challenge['category']}** category!"
                ),
                colour=discord.Colour.dark_gold(),
            )
            .set_thumbnail(url=interaction.user.display_avatar.url)
            .set_footer(text=challenge["solve_time"])
        )
        announcement = await solves_channel.send(embed=embed)

        challenge["solve_announcement"] = announcement.id
        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {
                "$set": {
                    "solved": challenge["solved"],
                    "solve_time": challenge["solve_time"],
                    "solve_announcement": challenge["solve_announcement"],
                    "players": challenge["players"],
                }
            },
        )

        await interaction.followup.send("✅ Challenge solved.")

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def unsolve(self, interaction: discord.Interaction) -> None:
        """Mark the challenge as not solved.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.defer()

        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
            {"channel": interaction.channel_id}
        )
        if challenge is None:
            # If we didn't find any challenge that corresponds to the channel from which
            # the command was run, then we're probably in a non-challenge channel.
            await interaction.followup.send(
                "You may only run this command in the channel associated to the "
                "challenge.",
                ephemeral=True,
            )

        # Check if challenge is already not solved.
        if not challenge["solved"]:
            await interaction.followup.send(
                "This challenge is already marked as not solved.", ephemeral=True
            )
            return

        try:
            await interaction.channel.edit(
                name=interaction.channel.name.replace("✅", "❌").replace("🩸", "❌")
            )
        except HTTPException:
            # We've exceeded the 2 channel edit per 10 min set by Discord.
            # This should only happen during testing, or when the users are trolling
            # by spamming solve and unsolve.
            pass

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        # Delete the challenge solved announcement we made.
        solves_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["solves"]
        )
        announcement = await solves_channel.fetch_message(
            challenge["solve_announcement"]
        )
        if announcement:
            await announcement.delete()

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {
                "$set": {
                    "solved": False,
                    "blooded": False,
                    "solve_time": None,
                    "solve_announcement": None,
                }
            },
        )

        await interaction.followup.send("✅ Challenge unsolved.")

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_challenge_autocompletion_func)
    @_in_ctf_channel()
    async def workon(self, interaction: discord.Interaction, name: str) -> None:
        """Start working on a challenge and join its channel.

        Args:
            interaction: The interaction that triggered this command.
            name: Challenge name (case insensitive).
        """
        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one({"name": name})
        if challenge is None:
            await interaction.response.send_message(
                "No such challenge.", ephemeral=True
            )
            return

        if interaction.user.name in challenge["players"]:
            await interaction.response.send_message(
                "You're already working on this challenge.", ephemeral=True
            )
            return

        if challenge["solved"]:
            await interaction.response.send_message(
                "You can't work on a challenge that has been solved.", ephemeral=True
            )
            return

        challenge["players"].append(interaction.user.name)

        challenge_channel = discord.utils.get(
            interaction.guild.text_channels, id=challenge["channel"]
        )

        await challenge_channel.set_permissions(interaction.user, read_messages=True)

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

        await interaction.response.send_message(
            f"✅ Added to the `{challenge['name']}` challenge."
        )
        await challenge_channel.send(
            f"{interaction.user.mention} wants to collaborate 🤝"
        )

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_challenge_autocompletion_func)
    @_in_ctf_channel()
    async def unworkon(
        self, interaction: discord.Interaction, name: Optional[str] = None
    ) -> None:
        """Stop working on a challenge and leave its channel (default: current
        channel's challenge).

        Args:
            interaction: The interaction that triggered this command.
            name: Challenge name (case insensitive).
        """
        if name is None:
            challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
                {"channel": interaction.channel_id}
            )
            if challenge is None:
                await interaction.response.send_message(
                    (
                        "Run this command from within a challenge channel, "
                        "or provide the name of the challenge you wish to stop "
                        "working on."
                    ),
                    ephemeral=True,
                )
                return
        else:
            challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one({"name": name})
            if challenge is None:
                await interaction.response.send_message(
                    "No such challenge.", ephemeral=True
                )
                return

        if interaction.user.name not in challenge["players"]:
            await interaction.response.send_message(
                "You're not working on this challenge in the first place.",
                ephemeral=True,
            )
            return

        challenge["players"].remove(interaction.user.name)

        challenge_channel = discord.utils.get(
            interaction.guild.text_channels, id=challenge["channel"]
        )

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

        await interaction.response.send_message(
            f"✅ Removed from the `{challenge['name']}` challenge.", ephemeral=True
        )
        await challenge_channel.send(
            f"{interaction.user.mention} left you alone, what a chicken! 🐥"
        )

        await challenge_channel.set_permissions(interaction.user, overwrite=None)

    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.autocomplete(name=_ctf_autocompletion_func)
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

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )

        # CTF name wasn't provided, and we're outside a CTF category channel, so
        # we display statuses of all running CTFs.
        if ctf is None and name is None:
            ctfs = MONGO[DBNAME][CTF_COLLECTION].find({"archived": False})
        # CTF name wasn't provided, and we're inside a CTF category channel, so
        # we display status of the CTF related to this category channel.
        elif name is None:
            ctfs = [ctf]
        # CTF name was provided, and we're inside a CTF category channel, so
        # the priority here is for the provided CTF name.
        # - or -
        # CTF name was provided, and we're outside a CTF category channel, so
        # we display status of the requested CTF only.
        else:
            ctfs = MONGO[DBNAME][CTF_COLLECTION].find_one(
                {"name": name, "archived": False}
            )
            if ctfs is None:
                await interaction.followup.send("No such CTF.", ephemeral=True)
                return
            ctfs = [ctfs]

        no_running_ctfs = True
        for ctf in ctfs:
            # Let the user know that they should join the CTF first to see its
            # details in case the command was run from outside the CTF channel.
            if ctf["guild_category"] != interaction.channel.category_id:
                embed = discord.Embed(
                    title=f"{ctf['name']} status",
                    colour=discord.Colour.blue(),
                    description=(
                        "You must run the command in one of the CTF's channels to see "
                        "its details."
                    ),
                )
                await interaction.followup.send(embed=embed)
                return

            # Otherwise, display details about the CTF status.
            challenges = ctf["challenges"]
            if not challenges:
                embed = discord.Embed(
                    title=f"{ctf['name']} status",
                    description="No challenges added yet.",
                    colour=discord.Colour.blue(),
                )
                await interaction.followup.send(embed=embed)
                return

            embed = None
            num_fields = 0
            for idx, challenge_id in enumerate(challenges):
                # If we reached Discord's maximum number of fields per
                # embed, we send the previous one and create a new one.
                if num_fields % 25 == 0:
                    if num_fields != 0:
                        await interaction.followup.send(embed=embed)
                        embed = None

                    if embed is None:
                        embed = discord.Embed(
                            title=f"{ctf['name']} status",
                            colour=discord.Colour.blue(),
                        )

                challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(challenge_id)
                if challenge["solved"] and mode == CTFStatusMode.all:
                    icon = "🩸" if challenge["blooded"] else "✅"
                    embed.add_field(
                        name=(f"{icon} {challenge['name']} ({challenge['category']})"),
                        value=(
                            "```diff\n"
                            f"+ Solver{['', 's'][len(challenge['players'])>1]}:"
                            f" {', '.join(challenge['players']).strip()}\n"
                            f"+ Date: {challenge['solve_time']}\n"
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
                            f"! Worker{['', 's'][len(challenge['players'])>1]}:"
                            f" {', '.join(challenge['players']).strip()}\n"
                            "```"
                        )
                    )
                    embed.add_field(
                        name=(
                            f"❌ {idx + 1:2} - "
                            f"{challenge['name']} ({challenge['category']})"
                        ),
                        value=workers,
                        inline=False,
                    )
                    num_fields += 1

            # Send the remaining embed.
            await interaction.followup.send(embed=embed)
            no_running_ctfs = False

        if no_running_ctfs:
            if name is None:
                await interaction.followup.send("No running CTFs.", ephemeral=True)
            else:
                await interaction.followup.send("No such CTF.", ephemeral=True)

    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def addcreds(
        self, interaction: discord.Interaction, username: str, password: str, url: str
    ) -> None:
        """Add credentials for the current CTF.

        Args:
            interaction: The interaction that triggered this command.
            username: The username to login with.
            password: The password to login with.
            url: URL of the CTF platform.
        """
        await interaction.response.defer()

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctf["credentials"]["url"] = url
        ctf["credentials"]["username"] = username
        ctf["credentials"]["password"] = password

        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]},
            {"$set": {"credentials": ctf["credentials"]}},
        )

        creds_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
        )
        message = (
            "```yaml\n"
            f"CTF platform: {url}\n"
            f"Username: {username}\n"
            f"Password: {password}\n"
            "```"
        )

        await creds_channel.purge()
        await creds_channel.send(message)
        await interaction.followup.send("✅ Credentials added.")

    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def showcreds(self, interaction: discord.Interaction) -> None:
        """Show credentials for the current CTF.

        Args:
            interaction: The interaction that triggered this command.
        """
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        url = ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        if url is None:
            await interaction.response.send_message(
                "No credentials set for this CTF.", ephemeral=True
            )
        else:
            message = (
                "```yaml\n"
                f"CTF platform: {url}\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                "```"
            )

            await interaction.response.send_message(message)

    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def pull(
        self, interaction: discord.Interaction, ctfd_url: Optional[str] = None
    ) -> None:
        """Pull challenges from the CTFd platform.

        Args:
            interaction: The interaction that triggered this command.
            ctfd_url: URL of the CTFd platform (default: url from the previously
                configured credentials).
        """
        await interaction.response.defer()

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        url = ctfd_url or ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        if url is None:
            await interaction.followup.send(
                "No credentials set for this CTF.", ephemeral=True
            )
            return

        async for challenge in pull_challenges(url, username, password):
            # Avoid having duplicate categories when people mix up upper/lower case
            # or add unnecessary spaces at the beginning or the end.
            challenge["category"] = challenge["category"].title().strip()

            # Check if challenge was already created.
            if MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
                {
                    "id": challenge["id"],
                    "name": challenge["name"],
                    "category": challenge["category"],
                }
            ):
                continue

            # Create a channel for the challenge and set its permissions.
            category_channel = discord.utils.get(
                interaction.guild.categories, id=interaction.channel.category_id
            )
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(
                    read_messages=False
                )
            }
            channel_name = sanitize_channel_name(
                f"{challenge['category']}-{challenge['name']}"
            )
            challenge_channel = await interaction.guild.create_text_channel(
                name=f"❌-{channel_name}",
                category=category_channel,
                overwrites=overwrites,
            )

            # Add challenge to the database.
            challenge_object_id = (
                MONGO[DBNAME][CHALLENGE_COLLECTION]
                .insert_one(
                    {
                        "id": challenge["id"],
                        "name": challenge["name"],
                        "category": challenge["category"],
                        "channel": challenge_channel.id,
                        "solved": False,
                        "blooded": False,
                        "players": [],
                        "solve_time": None,
                        "solve_announcement": None,
                    }
                )
                .inserted_id
            )

            # Add reference to the newly created challenge.
            ctf["challenges"].append(challenge_object_id)
            MONGO[DBNAME][CTF_COLLECTION].update_one(
                {"_id": ctf["_id"]}, {"$set": {"challenges": ctf["challenges"]}}
            )

            # Send challenge information in its respective channel.
            description = challenge["description"] or "No description."
            tags = ", ".join(challenge["tags"]) or "No tags."
            files = [
                f"{ctf['credentials']['url'].strip('/')}{file}"
                for file in challenge["files"]
            ]
            files = "\n- " + "\n- ".join(files) if files else "No files."
            embed = discord.Embed(
                title=f"{challenge['name']} - {challenge['value']} points",
                description=(
                    f"**Category:** {challenge['category']}\n"
                    f"**Description:** {description}\n"
                    f"**Files:** {files}\n"
                    f"**Tags:** {tags}"
                ),
                colour=discord.Colour.blue(),
            ).set_footer(
                text=datetime.strftime(datetime.now(tz=timezone.utc), DATE_FORMAT)
            )
            message = await challenge_channel.send(embed=embed)
            await message.pin()

            # Announce that the challenge was added.
            announcements_channel = discord.utils.get(
                interaction.guild.text_channels,
                id=ctf["guild_channels"]["announcements"],
            )
            role = discord.utils.get(interaction.guild.roles, id=ctf["guild_role"])

            embed = discord.Embed(
                title="🔔 New challenge created!",
                description=(
                    f"**Challenge name:** {challenge['name']}\n"
                    f"**Category:** {challenge['category']}\n\n"
                    f"Use `/ctf workon {challenge['name']}` or the button to join.\n"
                    f"{role.mention}"
                ),
                colour=discord.Colour.dark_gold(),
            ).set_footer(
                text=datetime.strftime(datetime.now(tz=timezone.utc), DATE_FORMAT)
            )
            await announcements_channel.send(
                embed=embed, view=WorkonButton(name=challenge["name"])
            )

        await interaction.followup.send("✅ Done pulling challenges")

    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command()
    @_in_ctf_channel()
    async def takenote(
        self,
        interaction: discord.Interaction,
        note_type: NoteType,
        note_format: Optional[NoteFormat] = NoteFormat.embed,
    ) -> None:
        """Copy the last message into the notes channel.

        Args:
            interaction: The interaction that triggered this command.
            note_type: Whether the note is about a challenge progress or otherwise
                (default: progress).
            note_format: Whether to create an embed for the note or take it as
                is (default: embed).
        """
        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one(
            {"channel": interaction.channel_id}
        )
        if challenge is None:
            await interaction.response.send_message(
                "❌ Not within a challenge channel.", ephemeral=True
            )
            return

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        notes_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["notes"]
        )

        # Get last message.
        async for message in interaction.channel.history(limit=1):
            break
        else:
            await interaction.response.send_message(
                "Nothing to take note of.", ephemeral=True
            )
            return

        if note_type == NoteType.progress:
            title = (
                f"🔄 **Challenge progress - "
                f"{challenge['name']} ({challenge['category']})**"
            )
            colour = discord.Colour.red()
        else:
            title = "📝 **Note**"
            colour = discord.Colour.green()

        if note_format == NoteFormat.embed:
            embed = (
                discord.Embed(
                    title=title,
                    description=message.content,
                    colour=colour,
                )
                .set_thumbnail(url=interaction.user.display_avatar.url)
                .set_author(name=interaction.user.name)
                .set_footer(text=datetime.now(tz=timezone.utc).strftime(DATE_FORMAT))
            )
            await notes_channel.send(embed=embed)
        else:
            embed = (
                discord.Embed(
                    title=title,
                    colour=colour,
                )
                .set_thumbnail(url=interaction.user.display_avatar.url)
                .set_author(name=interaction.user.name)
                .set_footer(text=datetime.now(tz=timezone.utc).strftime(DATE_FORMAT))
            )
            # If we send the embed and the content in the same command, the embed
            # would be placed after the content, which is not what we want.
            await notes_channel.send(embed=embed)
            await notes_channel.send(
                message.content,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )

        await interaction.response.send_message(
            "✅ Note taken successfully", ephemeral=True
        )

    @app_commands.command()
    @_in_ctf_channel()
    async def submit(self, interaction: discord.Interaction) -> None:
        """Submit a flag to the CTFd platform.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.send_modal(FlagSubmissionForm())

    @app_commands.command()
    @_in_ctf_channel()
    async def scoreboard(self, interaction: discord.Interaction) -> None:
        """Display scoreboard for the current CTF.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.defer()

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctfd_url = ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        teams = await get_scoreboard(ctfd_url, username, password)
        if teams is None:
            await interaction.response.send_message(
                "Failed to fetch the scoreboard.", ephemeral=True
            )
            return

        name_field_width = max(len(team["name"]) for team in teams) + 10
        scoreboard = ""
        for rank, team in enumerate(teams, start=1):
            scoreboard += (
                f"{['-', '+'][team['name'] == username]} "
                f"{rank:<10}{team['name']:<{name_field_width}}"
                f"{round(team['score'], 4)}\n"
            )

        if scoreboard:
            message = (
                "```diff\n"
                f"  {'Rank':<10}{'Team':<{name_field_width}}{'Score'}\n"
                f"{scoreboard}"
                "```"
            )
        else:
            message = "No solves yet, or platform isn't CTFd."

        # Update scoreboard in the scoreboard channel.
        scoreboard_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
        )
        async for last_message in scoreboard_channel.history(limit=1):
            await last_message.edit(content=message)
            break
        else:
            await scoreboard_channel.send(message)

        await interaction.followup.send(message)
