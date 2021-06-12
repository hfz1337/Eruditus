from typing import List, Union
from datetime import datetime
from pymongo import MongoClient

import discord
from discord import Member, TextChannel
from discord.ext.commands import Bot, Context
from discord.ext import tasks, commands

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from cogs.ctf.help import cog_help

from lib.util import sanitize_channel_name, derive_colour
from lib.ctfd import pull_challenges, submit_flag, get_scoreboard

from config import (
    MONGODB_URI,
    DBNAME_PREFIX,
    CHALLENGE_COLLECTION,
    CONFIG_COLLECTION,
    CTF_COLLECTION,
    DATE_FORMAT,
)


# MongoDB handle
mongo = MongoClient(MONGODB_URI)


def in_ctf_channel() -> bool:
    """Wrapper function to check if a command was issued from a CTF channel."""

    async def predicate(ctx: SlashContext) -> bool:
        if mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        ):
            return True

        await ctx.send(
            "You must be in a created CTF channel to use this command.", hidden=True
        )
        return False

    return commands.check(predicate)


class CTF(commands.Cog):
    """This cog provides the core functionality of the bot, i.e, the management of
    CTF competitions, members' participation, etc.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._updaters = {}

    async def _periodic_updater(self, ctx: SlashContext) -> None:
        """Pull new challenges from the CTFd platform and update the scoreboard
        periodically.
        """
        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        scoreboard_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
        )
        await self._scoreboard.invoke(ctx, scoreboard_channel)
        await self._pull.invoke(ctx)

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["createctf"]["name"],
        description=cog_help["subcommands"]["createctf"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["createctf"]["options"]
        ],
    )
    async def createctf(self, ctx: Union[SlashContext, Context], name: str) -> None:
        """Create a new CTF along with its role and private channels.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the CTF to create.
        """
        # Check if CTF already exists
        if mongo[f"{DBNAME_PREFIX}-{ctx.guild.id}"][CTF_COLLECTION].find_one(
            {"name": name}
        ):
            # Only send the message if the command was invoked by a member.
            # When a member invokes the command, it will be a SlashContext instance.
            if isinstance(ctx, SlashContext):
                await ctx.send(
                    "Another CTF with similar name already exists, please choose "
                    "another name.",
                    hidden=True,
                )
            return

        if isinstance(ctx, SlashContext):
            await ctx.defer()

        role = discord.utils.get(ctx.guild.roles, name=name)
        if role is None:
            role = await ctx.guild.create_role(
                name=name,
                colour=derive_colour(name),
                mentionable=True,
            )

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True),
        }

        category_channel = discord.utils.get(ctx.guild.categories, name=name)
        if category_channel is None:
            # If the command was invoked by us, then the CTF probably didn't start yet,
            # the emoji will be set to a clock, and once the CTF starts it will be
            # substituted with a red dot.
            emoji = "⏰" if ctx.author.id == self._bot.user.id else "🔴"
            category_channel = await ctx.guild.create_category(
                name=f"{emoji} {name}",
                overwrites=overwrites,
            )

        await ctx.guild.create_text_channel("general", category=category_channel)
        await ctx.guild.create_voice_channel("general", category=category_channel)

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        }

        credentials_channel = await ctx.guild.create_text_channel(
            name="🔑-credentials", category=category_channel, overwrites=overwrites
        )
        notes_channel = await ctx.guild.create_text_channel(
            name="📝-notes", category=category_channel, overwrites=overwrites
        )
        announcement_channel = await ctx.guild.create_text_channel(
            name="📣-announcements", category=category_channel, overwrites=overwrites
        )
        solves_channel = await ctx.guild.create_text_channel(
            name="🎉-solves", category=category_channel, overwrites=overwrites
        )
        scoreboard_channel = await ctx.guild.create_text_channel(
            name="📈-scoreboard", category=category_channel, overwrites=overwrites
        )

        ctf = {
            "name": name,
            "archived": False,
            "credentials": {
                "url": None,
                "username": None,
                "password": None,
            },
            "challenges": [],
            "guild_role": role.id,
            "guild_category": category_channel.id,
            "guild_channels": {
                "announcements": announcement_channel.id,
                "credentials": credentials_channel.id,
                "scoreboard": scoreboard_channel.id,
                "solves": solves_channel.id,
                "notes": notes_channel.id,
            },
        }
        mongo[f"{DBNAME_PREFIX}-{ctx.guild.id}"][CTF_COLLECTION].insert_one(ctf)
        # If the command was invoked by us (and thus `ctx` would be of type Context),
        # don't send the confirmation message.
        if isinstance(ctx, SlashContext):
            await ctx.send(f'✅ CTF "{name}" has been created')

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["renamectf"]["name"],
        description=cog_help["subcommands"]["renamectf"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["renamectf"]["options"]
        ],
    )
    async def _renamectf(self, ctx: SlashContext, new_name: str) -> None:
        """Rename a previously created CTF.

        Args:
            ctx: The context in which the command is being invoked under.
            new_name: The new CTF name.
        """
        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        old_name = ctf["name"]
        ctf["name"] = new_name

        category_channel = discord.utils.get(
            ctx.guild.categories, id=ctf["guild_category"]
        )

        await category_channel.edit(
            name=category_channel.name.replace(old_name, new_name)
        )

        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]}, {"$set": {"name": ctf["name"]}}
        )
        await ctx.send(f'✅ CTF "{old_name}" has been renamed to "{new_name}"')

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["archivectf"]["name"],
        description=cog_help["subcommands"]["archivectf"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["archivectf"]["options"]
        ],
    )
    async def _archivectf(
        self, ctx: SlashContext, mode: str = "minimal", name: str = None
    ):
        """Archive a CTF by making its channels read-only.

        Args:
            ctx: The context in which the command is being invoked under.
            mode: The archiving mode, whether to archive all the channels or
                the important ones only.
            name: Name of the CTF to archive. Defaults to the CTF associated to the
                category channel from which the command was issued.
        """
        await ctx.defer()

        if name is None:
            ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
                {"guild_category": ctx.channel.category_id}
            )
        else:
            ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
                {"name": name}
            )

        if ctf:
            # Stop periodic updater
            if ctf["credentials"]["url"] in self._updaters:
                self._updaters[ctf["credentials"]["url"]].cancel()
                del self._updaters[ctf["credentials"]["url"]]

            # Post challenge solves summary in the scoreboard channel
            summary = ""
            for challenge_id in ctf["challenges"]:
                challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                    CHALLENGE_COLLECTION
                ].find_one(challenge_id)
                summary += (
                    f"{['-', '+'][challenge['solved']]} "
                    f"{challenge['name']:<30}"
                    f"{challenge['category']:<30}"
                    f"{['❌', '✔️'][challenge['solved']]}\n"
                )

            if summary:
                summary = (
                    "```diff\n"
                    f"  {'Challenge':<30}{'Category':<30}{'Solved'}\n\n"
                    f"{summary}"
                    "```"
                )
                scoreboard_channel = discord.utils.get(
                    ctx.guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
                )
                await scoreboard_channel.send(summary)

            # Global archive category channel
            archive_category_channel = discord.utils.get(
                ctx.guild.categories,
                id=mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                    CONFIG_COLLECTION
                ].find_one()["archive_category_channel"],
            )

            # Category channel of the CTF
            category_channel = discord.utils.get(
                ctx.guild.categories, id=ctf["guild_category"]
            )

            if mode == "minimal":
                # Delete all channels for that CTF except the notes channel, which will
                # be moved to the global CTF archive
                for ctf_channel in category_channel.channels:
                    if ctf_channel.id == ctf["guild_channels"]["notes"]:
                        await ctf_channel.edit(
                            name=f"📝-{sanitize_channel_name(ctf['name'])}",
                            category=archive_category_channel,
                            sync_permissions=True,
                        )
                    elif ctf_channel.id == ctf["guild_channels"]["solves"]:
                        await ctf_channel.edit(
                            name=f"🎉-{sanitize_channel_name(ctf['name'])}",
                            category=archive_category_channel,
                            sync_permissions=True,
                        )
                    elif ctf_channel.id == ctf["guild_channels"]["scoreboard"]:
                        await ctf_channel.edit(
                            name=f"📈-{sanitize_channel_name(ctf['name'])}",
                            category=archive_category_channel,
                            sync_permissions=True,
                        )
                    else:
                        await ctf_channel.delete()
                # Finally, delete the category channel of the CTF
                await category_channel.delete()
            else:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        send_messages=False
                    )
                }
                # Make the category world readable, but not world writable
                await category_channel.edit(
                    name=f"🔒 {ctf['name']}",
                    overwrites=overwrites,
                )
                # Sync the channels' permissions with the category
                for ctf_channel in category_channel.channels:
                    await ctf_channel.edit(sync_permissions=True)

            role = discord.utils.get(ctx.guild.roles, id=ctf["guild_role"])
            if role is not None:
                await role.delete()

            # Delete all challenges for that CTF
            for challenge_id in ctf["challenges"]:
                mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                    CHALLENGE_COLLECTION
                ].delete_one({"_id": challenge_id})

            mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].update_one(
                {"_id": ctf["_id"]}, {"$set": {"archived": True}}
            )
            if ctx.channel is not None:
                await ctx.send(f"✅ CTF \"{ctf['name']}\" has been archived")
        else:
            await ctx.send("No such CTF.", hidden=True)

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["deletectf"]["name"],
        description=cog_help["subcommands"]["deletectf"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["deletectf"]["options"]
        ],
    )
    async def _deletectf(self, ctx: SlashContext, name: str = None) -> None:
        """Delete a CTF.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the CTF to delete. Defaults to the CTF associated with the
                category channel from which the command was issued.
        """
        await ctx.defer()

        if name is None:
            ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
                {"guild_category": ctx.channel.category_id}
            )
        else:
            ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
                {"name": name}
            )

        if ctf:
            # Stop periodic updater
            if ctf["credentials"]["url"] in self._updaters:
                self._updaters[ctf["credentials"]["url"]].cancel()
                del self._updaters[ctf["credentials"]["url"]]

            category_channel = discord.utils.get(
                ctx.guild.categories, id=ctf["guild_category"]
            )
            role = discord.utils.get(ctx.guild.roles, id=ctf["guild_role"])

            # `category_channel` can be None if the CTF we wish to delete was archived
            # using the ̀minimal` mode, we have to search inside the global CTF archive
            # category channel
            if category_channel is None:
                archive_category_channel = discord.utils.get(
                    ctx.guild.categories,
                    id=mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                        CONFIG_COLLECTION
                    ].find_one()["archive_category_channel"],
                )
                # Delete `notes`, `solves` and `scoreboard` channels for that CTF
                if archive_category_channel:
                    for ctf_channel in archive_category_channel.channels:
                        if (
                            ctf_channel.id == ctf["guild_channels"]["notes"]
                            or ctf_channel.id == ctf["guild_channels"]["solves"]
                            or ctf_channel.id == ctf["guild_channels"]["scoreboard"]
                        ):
                            await ctf_channel.delete()
            else:
                for ctf_channel in category_channel.channels:
                    await ctf_channel.delete()
                await category_channel.delete()

            if role is not None:
                await role.delete()

            # Delete all challenges for that CTF
            for challenge_id in ctf["challenges"]:
                mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                    CHALLENGE_COLLECTION
                ].delete_one({"_id": challenge_id})
            # Delete the CTF
            mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].delete_one(
                {"_id": ctf["_id"]}
            )

            await ctx.send(f"✅ CTF \"{ctf['name']}\" has been deleted")
        else:
            await ctx.send("No such CTF.", hidden=True)

    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["join"]["name"],
        description=cog_help["subcommands"]["join"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["join"]["options"]
        ],
    )
    async def _join(self, ctx: SlashContext, name: str) -> None:
        """Allow a member to join a CTF by granting the associated role.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the CTF to join.
        """
        role = discord.utils.get(ctx.guild.roles, name=name)
        if role is None:
            await ctx.send("No such CTF.", hidden=True)
        else:
            await ctx.author.add_roles(role)

            # Announce that the user joined the CTF
            ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
                {"guild_role": role.id}
            )
            if not ctf:
                return

            ctf_general_channel = discord.utils.get(
                ctx.guild.text_channels,
                category_id=ctf["guild_category"],
                name="general",
            )
            await ctx.send(f"✅ Added to \"{ctf['name']}\"")
            await ctf_general_channel.send(f"{ctx.author.mention} joined the battle ⚔️")

    @commands.bot_has_permissions(manage_roles=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["leave"]["name"],
        description=cog_help["subcommands"]["leave"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["leave"]["options"]
        ],
    )
    async def _leave(self, ctx: SlashContext) -> None:
        """Remove a member from the CTF by taking away the associated role.

        Args:
            ctx: The context in which the command is being invoked under.
        """
        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        role = discord.utils.get(ctx.guild.roles, id=ctf["guild_role"])

        # Announce that the user left the CTF
        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_role": role.id}
        )
        if not ctf:
            return

        ctf_general_channel = discord.utils.get(
            ctx.guild.text_channels,
            category_id=ctf["guild_category"],
            name="general",
        )
        await ctx.send(f"✅ Removed from \"{ctf['name']}\"", hidden=True)
        await ctf_general_channel.send(
            f"{ctx.author.mention} abandonned the boat :frowning:"
        )

        # Remove role and permissions
        for challenge in mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].find():
            if ctx.author.name in challenge["players"]:
                challenge_channel = discord.utils.get(
                    ctx.guild.text_channels, id=challenge["channel"]
                )
                await challenge_channel.set_permissions(ctx.author, overwrite=None)
        await ctx.author.remove_roles(role)

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["createchallenge"]["name"],
        description=cog_help["subcommands"]["createchallenge"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["createchallenge"]["options"]
        ],
    )
    async def _createchallenge(
        self,
        ctx: SlashContext,
        name: str,
        category: str,
        id: int = None,
        value: int = None,
        description: str = None,
        tags: List[str] = None,
        files: List[str] = None,
    ) -> None:
        """Create a new challenge for the CTF.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the challenge.
            category: Category of the challenge.
            id: CTFd challenge ID. Defaults to None.
            value: Value of the challenge. Defaults to None.
            description: Description of the challenge. Defaults to None.
            tags: Tags of the challenge. Defaults to None.
            files: Attachments provided with the challenge. Defaults to None.
        """
        # Avoid having duplicate categories when people mix up upper/lower case
        # or add unnecessary spaces at the beginning or the end.
        category = category.title().strip()

        # Check if challenge already exists
        if mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].find_one(
            {
                "name": name,
                "category": category,
            }
        ):
            if id is None:
                await ctx.send("This challenge already exists.", hidden=True)
            return

        # Create a channel for the challenge and set its permissions
        category_channel = discord.utils.get(
            ctx.guild.categories, id=ctx.channel.category_id
        )
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False)
        }
        channel_name = sanitize_channel_name(f"{category}-{name}")
        challenge_channel = await ctx.guild.create_text_channel(
            name=f"❌-{channel_name}",
            category=category_channel,
            overwrites=overwrites,
        )

        # Add challenge to the database
        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].insert_one(
            {
                "id": id,
                "name": name,
                "category": category,
                "channel": challenge_channel.id,
                "solved": False,
                "players": [],
                "solvers": [],
                "solve_time": None,
                "solve_announcement": None,
            }
        )

        # Add reference for the CTF to the newly created challenge
        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        ctf["challenges"].append(challenge.inserted_id)
        ctf_object_id = ctf["_id"]
        del ctf["_id"]
        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].update_one(
            {"_id": ctf_object_id}, {"$set": ctf}
        )

        # Announce that the challenge was added
        announcements_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctf["guild_channels"]["announcements"]
        )
        role = discord.utils.get(ctx.guild.roles, id=ctf["guild_role"])

        embed = discord.Embed(
            title="🔔 New challenge created!",
            description=(
                f"**Challenge name:** {name}\n"
                f"**Category:** {category}\n\n"
                f"Use `/ctf workon {name}` or `/ctf workon {len(ctf['challenges'])}` "
                f"to join.\n{role.mention}"
            ),
            colour=discord.Colour.dark_gold(),
        ).set_footer(text=datetime.strftime(datetime.now(), DATE_FORMAT))
        await announcements_channel.send(embed=embed)

        # Send challenge information in its respective channel if the challenge
        # was grabbed from CTFd after the `pull` command was invoked
        if id is not None:
            description = description or "No description."
            tags = ", ".join(tags) or "No tags."
            files = [f"{ctf['credentials']['url'].strip('/')}{file}" for file in files]
            files = "\n- " + "\n- ".join(files) if files else "No files."
            embed = discord.Embed(
                title=f"{name} - {value} points",
                description=(
                    f"**Category:** {category}\n"
                    f"**Description:** {description}\n"
                    f"**Files:** {files}\n"
                    f"**Tags:** {tags}"
                ),
                colour=discord.Colour.blue(),
            ).set_footer(text=datetime.strftime(datetime.now(), DATE_FORMAT))
            message = await challenge_channel.send(embed=embed)
            await message.pin()
        else:
            await ctx.send("✅ Challenge created")

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["renamechallenge"]["name"],
        description=cog_help["subcommands"]["renamechallenge"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["renamechallenge"]["options"]
        ],
    )
    async def _renamechallenge(
        self, ctx: SlashContext, new_name: str, new_category: str = None
    ) -> None:
        """Rename a previously created challenge.

        Args:
            ctx: The context in which the command is being invoked under.
            new_name: New challenge name.
            new_category: New category of the challenge. Defaults to None, which means
                the category doesn't change and we stick to the previous one.
        """
        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].find_one({"channel": ctx.channel_id})

        challenge["name"] = new_name
        challenge["category"] = new_category or challenge["category"]
        new_channel_name = sanitize_channel_name(
            f"{challenge['category']}-{challenge['name']}"
        )

        challenge_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctx.channel_id
        )
        if challenge["solved"]:
            await challenge_channel.edit(name=f"✅-{new_channel_name}")
        else:
            await challenge_channel.edit(name=f"❌-{new_channel_name}")

        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"name": challenge["name"], "category": challenge["category"]}},
        )
        await ctx.send("✅ Challenge renamed")

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["deletechallenge"]["name"],
        description=cog_help["subcommands"]["deletechallenge"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["deletechallenge"]["options"]
        ],
    )
    async def _deletechallenge(self, ctx: SlashContext, name: str = None) -> None:
        """Delete a challenge from the CTF.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the challenge to delete. Defaults to None, which means
                deleting the challenge associated with the channel from which this
                command was issued.
        """
        if name is None:
            challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                CHALLENGE_COLLECTION
            ].find_one({"channel": ctx.channel_id})
        else:
            challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                CHALLENGE_COLLECTION
            ].find_one({"name": name})

        if challenge is None:
            await ctx.send("No such challenge.", hidden=True)
            return

        # Delete challenge from the database
        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].delete_one(
            challenge
        )

        # Delete reference to that challenge from the CTF
        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )

        # Delete channel associated with the challenge
        challenge_channel = discord.utils.get(
            ctx.guild.text_channels, id=challenge["channel"]
        )
        await challenge_channel.delete()

        ctf["challenges"].remove(challenge["_id"])
        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]}, {"$set": {"challenges": ctf["challenges"]}}
        )

        await ctx.send("✅ Challenge deleted")

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["solve"]["name"],
        description=cog_help["subcommands"]["solve"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["solve"]["options"]
        ],
    )
    async def _solve(
        self,
        ctx: SlashContext,
        **support: Member,
    ) -> None:
        """Mark the challenge solved, and make an announcement on the announcements
        channel.

        Args:
            ctx: The context in which the command is being invoked under.
            **support: One or more members who contributed solving the challenge.
        """
        await ctx.defer()

        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].find_one({"channel": ctx.channel_id})
        if challenge is None:
            # If we didn't find any challenge that corresponds to the channel from which
            # the command was run, then we're probably in a non-challenge channel.
            await ctx.send(
                "You may only run this command in the channel associated to the "
                "challenge.",
                hidden=True,
            )
            return

        # If the challenged was already solved
        if challenge["solved"]:
            await ctx.send("This challenge was already solved.", hidden=True)
            return

        solvers = [ctx.author.name] + [support[member].name for member in support]

        challenge["solved"] = True
        challenge["solvers"] = solvers
        challenge["solve_time"] = datetime.now().strftime(DATE_FORMAT)

        try:
            await ctx.channel.edit(name=ctx.channel.name.replace("❌", "✅"))
        except Exception:
            # We've exceeded the 2 channel edit per 10 min set by Discord
            # should only happen during testing, or when the users are trolling
            # by spamming solve and unsolve.
            pass

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        solves_channel = self._bot.get_channel(ctf["guild_channels"]["solves"])
        embed = (
            discord.Embed(
                title="🎉 Challenge solved!",
                description=(
                    f"**{', '.join(solvers)}** just solved "
                    f"**{challenge['name']}** from the "
                    f"**{challenge['category']}** category!"
                ),
                colour=discord.Colour.dark_gold(),
            )
            .set_thumbnail(url=ctx.author.avatar_url)
            .set_footer(text=challenge["solve_time"])
        )
        announcement = await solves_channel.send(embed=embed)

        challenge["solve_announcement"] = announcement.id
        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {
                "$set": {
                    "solved": challenge["solved"],
                    "solvers": challenge["solvers"],
                    "solve_time": challenge["solve_time"],
                    "solve_announcement": challenge["solve_announcement"],
                }
            },
        )

        await ctx.send("✅ Challenge solved")

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["unsolve"]["name"],
        description=cog_help["subcommands"]["unsolve"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["unsolve"]["options"]
        ],
    )
    async def _unsolve(self, ctx: SlashContext) -> None:
        """Mark a challenge unsolved and remove its associated announcement.

        Args:
            ctx: The context in which the command is being invoked under.
        """
        await ctx.defer()

        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].find_one({"channel": ctx.channel_id})
        if challenge is None:
            # If we didn't find any challenge that corresponds to the channel from which
            # the command was run, then we're probably in a non-challenge channel.
            await ctx.send(
                "You may only run this command in the channel associated to the "
                "challenge.",
                hidden=True,
            )

        # Check if challenge is already not solved
        if not challenge["solved"]:
            await ctx.send(
                "This challenge is already marked as not solved.", hidden=True
            )
            return

        try:
            await ctx.channel.edit(name=ctx.channel.name.replace("✅", "❌"))
        except Exception:
            # We've exceeded the 2 channel edit per 10 min set by Discord
            # should only happen during testing, or when the users are trolling
            # by spamming solve and unsolve.
            pass

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        # Delete the challenge solved announcement we made
        solves_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctf["guild_channels"]["solves"]
        )
        announcement = await solves_channel.fetch_message(
            challenge["solve_announcement"]
        )
        await announcement.delete()

        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {
                "$set": {
                    "solved": False,
                    "solvers": [],
                    "solve_time": None,
                    "solve_announcement": None,
                }
            },
        )

        await ctx.send("✅ Challenge unsolved")

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["workon"]["name"],
        description=cog_help["subcommands"]["workon"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["workon"]["options"]
        ],
    )
    async def _workon(self, ctx: SlashContext, name: Union[str, int]) -> None:
        """Add a member to a challenge by giving him access to the associated
        channel.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the challenge.
        """
        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].find_one({"name": name})

        if challenge is None and name.isdigit():
            position = int(name)
            ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
                {"guild_category": ctx.channel.category_id}
            )
            if 0 < position <= len(ctf["challenges"]):
                challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                    CHALLENGE_COLLECTION
                ].find_one(ctf["challenges"][position - 1])

        if challenge is None:
            await ctx.send("No such challenge.", hidden=True)
            return

        if ctx.author.name in challenge["players"]:
            await ctx.send("You're already working on this challenge.", hidden=True)
            return

        if challenge["solved"]:
            await ctx.send(
                "You can't work on a challenge that has been solved.", hidden=True
            )
            return

        challenge["players"].append(ctx.author.name)

        challenge_channel = discord.utils.get(
            ctx.guild.text_channels, id=challenge["channel"]
        )

        await challenge_channel.set_permissions(ctx.author, read_messages=True)

        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

        await ctx.send("✅ Added to the challenge")
        await challenge_channel.send(f"{ctx.author.mention} wants to collaborate 🤝")

    @commands.bot_has_permissions(manage_channels=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["unworkon"]["name"],
        description=cog_help["subcommands"]["unworkon"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["unworkon"]["options"]
        ],
    )
    async def _unworkon(self, ctx: SlashContext, name: Union[str, int] = None) -> None:
        """Remove a member from a challenge.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the challenge.
        """
        if name is None:
            challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                CHALLENGE_COLLECTION
            ].find_one({"channel": ctx.channel_id})
        else:
            challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                CHALLENGE_COLLECTION
            ].find_one({"name": name})

        if challenge is None and name.isdigit():
            position = int(name)
            ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
                {"guild_category": ctx.channel.category_id}
            )
            if 0 < position <= len(ctf["challenges"]):
                challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                    CHALLENGE_COLLECTION
                ].find_one(ctf["challenges"][position - 1])

        if challenge is None:
            await ctx.send("No such challenge.", hidden=True)
            return

        if ctx.author.name not in challenge["players"]:
            return

        challenge["players"].remove(ctx.author.name)

        challenge_channel = discord.utils.get(
            ctx.guild.text_channels, id=challenge["channel"]
        )

        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

        await ctx.send(f"✅ Removed from \"{challenge['name']}\"", hidden=True)
        await challenge_channel.send(
            f"{ctx.author.mention} left you alone, what a chicken! 🐥"
        )

        await challenge_channel.set_permissions(ctx.author, overwrite=None)

    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["status"]["name"],
        description=cog_help["subcommands"]["status"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["status"]["options"]
        ],
    )
    async def _status(self, ctx: SlashContext, name: str = None) -> None:
        """Show all ongoing CTF competitions, and provide details about a specific
        CTF if the command is issued from a CTF channel.

        Args:
            ctx: The context in which the command is being invoked under.
            name: Name of the CTF.
        """
        await ctx.defer()

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )

        # CTF name wasn't provided, and we're outside a CTF category channel, so
        # we display statuses of all running CTFs.
        if ctf is None and name is None:
            ctfs = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find(
                {"archived": False}
            )
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
            ctfs = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find(
                {"name": name, "archived": False}
            )

        no_running_ctfs = True
        for ctf in ctfs:
            # Display details about the CTF status only if the command was run in
            # one of that CTF's channels
            if ctf["guild_category"] == ctx.channel.category_id:
                challenges = ctf["challenges"]
                if not challenges:
                    embed = discord.Embed(
                        title=f"{ctf['name']} status",
                        description="No challenges added yet.",
                        colour=discord.Colour.blue(),
                    )
                    await ctx.send(embed=embed)
                else:
                    embed = None
                    for idx, challenge_id in enumerate(challenges):
                        # If we reached Discord's maximum number of fields per
                        # embed, we send the previous one and create a new one
                        if idx % 25 == 0:
                            if embed is not None:
                                await ctx.send(embed=embed)

                            embed = discord.Embed(
                                title=f"{ctf['name']} status",
                                colour=discord.Colour.blue(),
                            )

                        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                            CHALLENGE_COLLECTION
                        ].find_one(challenge_id)
                        if challenge["solved"]:
                            embed.add_field(
                                name=(
                                    f"✅ {challenge['name']} ({challenge['category']})"
                                ),
                                value=(
                                    "```diff\n"
                                    f"+ Solver{['', 's'][len(challenge['solvers'])>1]}:"
                                    f" {', '.join(challenge['solvers']).strip()}\n"
                                    f"+ Date: {challenge['solve_time']}\n"
                                    "```"
                                ),
                                inline=False,
                            )
                        else:
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
                    # Send the remaining embed
                    await ctx.send(embed=embed)

            # Otherwise, let the user know that they should join the CTF first to
            # see the details.
            else:
                embed = discord.Embed(
                    title=f"{ctf['name']} status",
                    colour=discord.Colour.blue(),
                    description=(
                        "You must run the command in one of the CTF's channels to see "
                        "its details."
                    ),
                )
                await ctx.send(embed=embed)

            no_running_ctfs = False

        if no_running_ctfs:
            if name is None:
                await ctx.send("No running CTFs.", hidden=True)
            else:
                await ctx.send("No such CTF.", hidden=True)

    @commands.bot_has_permissions(manage_messages=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["addcreds"]["name"],
        description=cog_help["subcommands"]["addcreds"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["addcreds"]["options"]
        ],
    )
    async def _addcreds(
        self, ctx: SlashContext, username: str, password: str, url: str
    ) -> None:
        """Add credentials for the CTF.

        Args:
            ctx: The context in which the command is being invoked under.
            username: The username to login with.
            password: The password to login with.
            url: The CTF platform where these credentials are intended to be used.
        """
        await ctx.defer()

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        ctf["credentials"]["url"] = url
        ctf["credentials"]["username"] = username
        ctf["credentials"]["password"] = password

        mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]},
            {"$set": {"credentials": ctf["credentials"]}},
        )

        creds_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctf["guild_channels"]["credentials"]
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
        await ctx.send("✅ Credentials added")

        # Start a background task for this CTF in order to pull new challenges
        # periodically
        self._updaters[ctf["credentials"]["url"]] = tasks.loop(
            minutes=1.0, reconnect=True
        )(self._periodic_updater)
        self._updaters[ctf["credentials"]["url"]].start(ctx)

    @commands.bot_has_permissions(manage_messages=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["showcreds"]["name"],
        description=cog_help["subcommands"]["showcreds"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["showcreds"]["options"]
        ],
    )
    async def _showcreds(self, ctx: SlashContext) -> None:
        """Show credentials of the CTF.

        Args:
            ctx: The context in which the command is being invoked under.
        """
        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        url = ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        if username is None or password is None or url is None:
            await ctx.send("No credentials set for this CTF.", hidden=True)
        else:
            message = (
                "```yaml\n"
                f"CTF platform: {url}\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                "```"
            )

            await ctx.send(message)

    @commands.bot_has_permissions(manage_messages=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["pull"]["name"],
        description=cog_help["subcommands"]["pull"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["pull"]["options"]
        ],
    )
    async def _pull(self, ctx: SlashContext, ctfd_url: str = None) -> None:
        """Pull new challenges from the CTFd platform.

        Args:
            ctx: The context in which the command is being invoked under.
            ctfd_url: URL of the CTFd platform. Defaults to None, which means taking
                the URL from the credentials previously set.
        """
        # Don't defer if we already responded to the interaction, this happens when
        # `pull` is invoked by `addcreds`
        if not ctx.responded:
            await ctx.defer()

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        url = ctfd_url or ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        if username is None or password is None or url is None:
            await ctx.send("No credentials set for this CTF.", hidden=True)
        else:
            async for challenge in pull_challenges(url, username, password):
                # Create this challenge if it didn't exist
                if not mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
                    CHALLENGE_COLLECTION
                ].find_one(
                    {
                        "id": challenge["id"],
                        "name": challenge["name"],
                        "category": challenge["category"],
                    }
                ):
                    await self._createchallenge.invoke(
                        ctx,
                        challenge["name"],
                        challenge["category"],
                        challenge["id"],
                        challenge["value"],
                        challenge["description"],
                        challenge["tags"],
                        challenge["files"],
                    )

            # If we already responded (which happens if `pull` if invoked through
            # `addcreds` or `_periodic_updater`), then don't send the confirmation
            # message, otherwise we would be spamming this same message everytime
            # the periodic updater is executed.
            if not ctx.responded:
                await ctx.send("✅ Done pulling challenges")

    @commands.bot_has_permissions(manage_messages=True)
    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["takenote"]["name"],
        description=cog_help["subcommands"]["takenote"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["takenote"]["options"]
        ],
    )
    async def _takenote(
        self, ctx: SlashContext, note_type: str, note_format: str = "embed"
    ) -> None:
        """Copy the last message in the channel into the notes channel.

        Args:
            ctx: The context in which the command is being invoked under.
            note_type: Whether the note is about a challenge progress or an info.
            note_format: Whether to copy the note in an embed (the default) or take
                it as is.
        """
        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].find_one({"channel": ctx.channel_id})
        if challenge is None:
            await ctx.send("❌ Not within a challenge channel", hidden=True)
            return

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        notes_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctf["guild_channels"]["notes"]
        )
        history = await ctx.channel.history(limit=1).flatten()
        message = history[0]

        if note_type == "progress":
            title = (
                f"🔄 **Challenge progress - "
                f"{challenge['name']} ({challenge['category']})**"
            )
            colour = discord.Colour.red()
        else:
            title = "📝 **Note**"
            colour = discord.Colour.green()

        if note_format == "embed":
            embed = (
                discord.Embed(
                    title=title,
                    description=message.clean_content,
                    colour=colour,
                )
                .set_thumbnail(url=ctx.author.avatar_url)
                .set_author(name=ctx.author.name)
                .set_footer(text=datetime.now().strftime(DATE_FORMAT).strip())
            )
            await notes_channel.send(embed=embed)
        else:
            embed = (
                discord.Embed(
                    title=title,
                    colour=colour,
                )
                .set_thumbnail(url=ctx.author.avatar_url)
                .set_author(name=ctx.author.name)
                .set_footer(text=datetime.now().strftime(DATE_FORMAT).strip())
            )
            # If we send the embed and the content in the same command, the embed
            # would be placed after the content, which is not what we want.
            await notes_channel.send(embed=embed)
            await notes_channel.send(
                message.clean_content,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )

        await ctx.send("✅ Note taken successfully", hidden=True)

    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["submit"]["name"],
        description=cog_help["subcommands"]["submit"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["submit"]["options"]
        ],
    )
    async def _submit(self, ctx: SlashContext, flag: str, **support: Member) -> None:
        """Submit a flag to the CTFd platform and inform us whether we got first
        blood.

        Args:
            ctx: The context in which the command is being invoked under.
            flag: The flag to submit
            **support: One or more members who helped solving the challenge.
        """
        await ctx.defer()

        challenge = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][
            CHALLENGE_COLLECTION
        ].find_one({"channel": ctx.channel_id})
        if challenge is None:
            await ctx.send(
                "❌ This command may only be used from within a challenge channel",
                hidden=True,
            )
            return

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        ctfd_url = ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        solvers = [ctx.author.name] + [support[member].name for member in support]

        status, first_blood = await submit_flag(
            ctfd_url, username, password, challenge["id"], flag
        )
        if status is None:
            await ctx.send("❌ Failed to submit the flag")
        elif status == "correct":
            # Mark challenge as solved (as if `/ctf solve` was called)
            challenge["solved"] = True
            challenge["solvers"] = solvers
            challenge["solve_time"] = datetime.now().strftime(DATE_FORMAT)

            solves_channel = self._bot.get_channel(ctf["guild_channels"]["solves"])

            if first_blood:
                await ctx.send("🩸 Well done, you got first blood!")
                embed = (
                    discord.Embed(
                        title="🩸 First blood!",
                        description=(
                            f"**{', '.join(solvers)}** just solved "
                            f"**{challenge['name']}** from the "
                            f"**{challenge['category']}** category!"
                        ),
                        colour=discord.Colour.red(),
                    )
                    .set_thumbnail(url=ctx.author.avatar_url)
                    .set_footer(text=challenge["solve_time"])
                )
            else:
                await ctx.send("✅ Well done, challenge solved!")
                embed = (
                    discord.Embed(
                        title="🎉 Challenge solved!",
                        description=(
                            f"**{', '.join(solvers)}** just solved "
                            f"**{challenge['name']}** from the "
                            f"**{challenge['category']}** category!"
                        ),
                        colour=discord.Colour.dark_gold(),
                    )
                    .set_thumbnail(url=ctx.author.avatar_url)
                    .set_footer(text=challenge["solve_time"])
                )
            announcement = await solves_channel.send(embed=embed)

            challenge_channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel"]
            )

            try:
                await challenge_channel.edit(name=ctx.channel.name.replace("❌", "✅"))
            except Exception:
                # We've exceeded the 2 channel edit per 10 min set by Discord
                # should only happen during testing, or when the users are trolling
                # by spamming solve and unsolve.
                pass

            challenge["solve_announcement"] = announcement.id

            mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CHALLENGE_COLLECTION].update_one(
                {"_id": challenge["_id"]},
                {
                    "$set": {
                        "solved": challenge["solved"],
                        "solvers": challenge["solvers"],
                        "solve_time": challenge["solve_time"],
                        "solve_announcement": challenge["solve_announcement"],
                    }
                },
            )
        elif status == "already_solved":
            await ctx.send("You already solved this challenge.")
        else:
            await ctx.send("❌ Incorrect flag.")

    @in_ctf_channel()
    @commands.guild_only()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["scoreboard"]["name"],
        description=cog_help["subcommands"]["scoreboard"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["scoreboard"]["options"]
        ],
    )
    async def _scoreboard(self, ctx: SlashContext, channel: TextChannel = None) -> None:
        """Display scoreboard for the current CTF.

        Args:
            ctx: The context in which the command is being invoked under.
        """
        if channel is None:
            await ctx.defer()

        ctf = mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTF_COLLECTION].find_one(
            {"guild_category": ctx.channel.category_id}
        )
        ctfd_url = ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        teams = await get_scoreboard(ctfd_url, username, password)

        scoreboard = ""
        for rank, team in enumerate(teams, start=1):
            scoreboard += (
                f"{['-', '+'][team['name'] == username]} "
                f"{rank:<10}{team['name']:<50}{round(team['score'], 4)}\n"
            )

        if scoreboard:
            message = (
                "```diff\n"
                f"  {'Rank':<10}{'Team':<50}{'Score'}\n"
                f"{scoreboard}"
                "```"
            )
        else:
            message = "No solves yet, or platform isn't CTFd."

        # If `channel` was provided (i.e, scoreboard channel), we fetch the scoreboard
        # message if it was already sent and update it
        if channel is not None:
            history = await channel.history(limit=1).flatten()
            if history:
                await history[0].edit(content=message)
            else:
                await channel.send(message)
        else:
            await ctx.send(message)


def setup(bot: Bot) -> None:
    """Add the extension to the bot."""
    bot.add_cog(CTF(bot))
