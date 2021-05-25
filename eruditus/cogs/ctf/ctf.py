#
# Eruditus - CTF cog
#
# ======================================================================================
# Implements the necessary functionalities to manage a CTF competition with ease:
# - Create a new CTF
# - Rename a previously created CTF
# - Archive a CTF (make its channels public and read-only)
# - Delete a CTF (SHOULD BE USED WITH CAUTION)
# - Join an ongoing CTF
# - Leave a previously joined CTF
# - Add CTF credentials and put them in a dedicated read-only channel
# - Show CTF credentials
# - Show that you're working on a specific challenge
# - Stop working on a challenge
# - Mark a challenge as solved
# - Mark a challenge as not solved
# - Create a new challenge
# - Rename a previously created challenge
# - Delete a previously created challenge
# - Submit a flag to the CTFd platform using /submit
# - Pull CTF challenges from the CTFd paltform
# - Show status of ongoing CTFs
# ======================================================================================

from typing import List
from datetime import datetime
from pymongo import MongoClient

import discord
from discord import Member
from discord.ext.commands import Bot
from discord.ext import tasks, commands

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from cogs.ctf.help import cog_help
from lib.util import sanitize_channel_name, derive_colour
from lib.ctfd import pull_challenges, submit_flag
from config import (
    MONGODB_URI,
    DBNAME,
    CTFS_COLLECTION,
    DATE_FORMAT,
    ARCHIVE_CATEGORY_CHANNEL,
)


# MongoDB handle
mongo = MongoClient(MONGODB_URI)[DBNAME]


def in_ctf_channel() -> bool:
    async def predicate(ctx: SlashContext) -> bool:
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        if ctf_info:
            return True

        await ctx.send("You must be in a created CTF channel to use this command.")
        return False

    return commands.check(predicate)


class CTF(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
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
    async def _createctf(self, ctx: SlashContext, name: str) -> None:
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
            # change by a red dot.
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

        ctf_info = {
            "name": name,
            "category_channel_id": category_channel.id,
            "role_id": role.id,
            "archived": False,
            "announcement_channel_id": announcement_channel.id,
            "notes_channel_id": notes_channel.id,
            "solves_channel_id": solves_channel.id,
            "challenges": [],
            "credentials": {
                "channel_id": credentials_channel.id,
                "url": None,
                "username": None,
                "password": None,
            },
        }
        mongo[CTFS_COLLECTION].update(
            {"category_channel_id": category_channel.id},
            {"$set": ctf_info},
            upsert=True,
        )
        # If the command was called by us, do nothing
        if ctx.author.id != self._bot.user.id:
            await ctx.send(f'✅ "{name}" has been created')

    @commands.bot_has_permissions(manage_channels=True)
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @in_ctf_channel()
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
        await ctx.defer()
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        old_name = ctf_info["name"]
        ctf_info["name"] = new_name

        category_channel = discord.utils.get(
            ctx.guild.categories, id=ctf_info["category_channel_id"]
        )

        await category_channel.edit(
            name=category_channel.name.replace(old_name, new_name)
        )

        mongo[CTFS_COLLECTION].update(
            {"_id": ctf_info["_id"]}, {"$set": {"name": ctf_info["name"]}}
        )
        await ctx.send(f'✅ CTF "{old_name}" has been renamed to "{new_name}"')

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
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
        await ctx.defer()

        if name is None:
            ctf_info = mongo[CTFS_COLLECTION].find_one(
                {"category_channel_id": ctx.channel.category_id}
            )
        else:
            ctf_info = mongo[CTFS_COLLECTION].find_one({"name": name})

        if ctf_info:
            # If the ARCHIVE_CATEGORY_CHANNEL is provided and it's numeric, check if
            # it corresponds to an existing category channel in the guild.
            if ARCHIVE_CATEGORY_CHANNEL and ARCHIVE_CATEGORY_CHANNEL.isdigit():
                archive_category_channel = discord.utils.get(
                    ctx.guild.categories, id=int(ARCHIVE_CATEGORY_CHANNEL)
                )
            else:
                archive_category_channel = None

            # If the provided category channel didn't exist, we try to fetch it from
            # the database
            if archive_category_channel is None:
                archive_category_channel = mongo[CTFS_COLLECTION].find_one(
                    {"archive_category_channel_id": {"$exists": True}}
                )
                # If the category channel was found in the database, we fetch it
                if archive_category_channel:
                    archive_category_channel_id = archive_category_channel[
                        "archive_category_channel_id"
                    ]
                    archive_category_channel = discord.utils.get(
                        ctx.guild.categories, id=archive_category_channel_id
                    )
                # If the category channel wasn't found in the database, or it was found
                # but got deleted from the server, we create a new archive category and
                # save its ID to the database for future use.
                if not archive_category_channel:
                    overwrites = {
                        ctx.guild.default_role: discord.PermissionOverwrite(
                            send_messages=False
                        )
                    }
                    archive_category_channel = await ctx.guild.create_category(
                        name="📁 CTF Archive",
                        overwrites=overwrites,
                    )
                    mongo[CTFS_COLLECTION].update(
                        {"archive_category_channel_id": {"$exists": True}},
                        {
                            "$set": {
                                "archive_category_channel_id": (
                                    archive_category_channel.id
                                )
                            }
                        },
                        upsert=True,
                    )

            category_channel = discord.utils.get(
                ctx.guild.categories, id=ctf_info["category_channel_id"]
            )

            if mode == "minimal":
                # Delete all channels for that CTF except the notes channel, which will
                # be moved to the global CTF archive
                for channel in category_channel.channels:
                    if channel.id == ctf_info["notes_channel_id"]:
                        await channel.edit(
                            name=f"📝-{sanitize_channel_name(ctf_info['name'])}",
                            category=archive_category_channel,
                            sync_permissions=True,
                        )
                    elif channel.id == ctf_info["solves_channel_id"]:
                        await channel.edit(
                            name=f"🎉-{sanitize_channel_name(ctf_info['name'])}",
                            category=archive_category_channel,
                            sync_permissions=True,
                        )
                    else:
                        await channel.delete()
                # Finally, delete the category channel of the CTF
                await category_channel.delete()
            else:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        send_messages=False
                    )
                }
                await category_channel.edit(
                    name=f"🔒 {ctf_info['name']}",
                    overwrites=overwrites,
                )
                for channel in category_channel.channels:
                    await channel.edit(sync_permissions=True)

            role = discord.utils.get(ctx.guild.roles, id=ctf_info["role_id"])
            if role is not None:
                await role.delete()

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]}, {"$set": {"archived": True}}
            )
            await ctx.send(f"✅ \"{ctf_info['name']}\" has been archived")
        else:
            await ctx.send("No such CTF.")

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
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
        await ctx.defer()
        if name is None:
            ctf_info = mongo[CTFS_COLLECTION].find_one(
                {"category_channel_id": ctx.channel.category_id}
            )
        else:
            ctf_info = mongo[CTFS_COLLECTION].find_one({"name": name})

        if ctf_info:
            category_channel = discord.utils.get(
                ctx.guild.categories, id=ctf_info["category_channel_id"]
            )
            role = discord.utils.get(ctx.guild.roles, id=ctf_info["role_id"])

            # `category_channel` can be None if the CTF we wish to delete was archived
            # using the ̀minimal` mode, we have to search inside the global CTF archive
            # category channel
            if category_channel is None:
                archive_category_channel = mongo[CTFS_COLLECTION].find_one(
                    {"archive_category_channel_id": {"$exists": True}}
                )
                if archive_category_channel:
                    archive_category_channel = discord.utils.get(
                        ctx.guild.categories,
                        id=archive_category_channel["archive_category_channel_id"],
                    )
                    # Delete `notes` and `solves` channels for that CTF
                    for channel in archive_category_channel.channels:
                        if (
                            channel.id == ctf_info["notes_channel_id"]
                            or channel.id == ctf_info["solves_channel_id"]
                        ):
                            await channel.delete()
            else:
                for channel in category_channel.channels:
                    await channel.delete()
                await category_channel.delete()

            if role is not None:
                await role.delete()

            mongo[CTFS_COLLECTION].delete_one({"_id": ctf_info["_id"]})
            await ctx.send(f"✅ \"{ctf_info['name']}\" has been deleted")
        else:
            await ctx.send("No such CTF.")

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
        await ctx.defer()
        role = discord.utils.get(ctx.guild.roles, name=name)

        if role is None:
            await ctx.send("No such CTF.")
        else:
            await ctx.author.add_roles(role)

            # Announce that the user joined the CTF
            ctf_info = mongo[CTFS_COLLECTION].find_one({"role_id": role.id})
            if not ctf_info:
                return

            ctf_general_channel = discord.utils.get(
                ctx.guild.text_channels,
                category_id=ctf_info["category_channel_id"],
                name="general",
            )
            await ctx.send(f"✅ Added to \"{ctf_info['name']}\"")
            await ctf_general_channel.send(f"{ctx.author.mention} joined the battle ⚔️")

    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    @in_ctf_channel()
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
        await ctx.defer()
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        role = discord.utils.get(ctx.guild.roles, id=ctf_info["role_id"])
        await ctx.author.remove_roles(role)

        # Announce that the user left the CTF
        ctf_info = mongo[CTFS_COLLECTION].find_one({"role_id": role.id})
        if not ctf_info:
            return

        ctf_general_channel = discord.utils.get(
            ctx.guild.text_channels,
            category_id=ctf_info["category_channel_id"],
            name="general",
        )
        await ctx.send(f"✅ Removed from \"{ctf_info['name']}\"")
        await ctf_general_channel.send(
            f"{ctx.author.mention} abandonned the boat :frowning:"
        )

    @commands.guild_only()
    @in_ctf_channel()
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
        # Avoid having duplicate categories when people mix up upper/lower case
        # or add unnecessary spaces at the beginning or the end.
        category = category.title().strip()

        category_channel_id = ctx.channel.category_id
        channel_name = sanitize_channel_name(f"{category}-{name}")
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": category_channel_id}
        )
        challenges = ctf_info["challenges"]

        if all(
            not (name == challenge["name"] and category == challenge["category"])
            for challenge in challenges
        ):
            category_channel = discord.utils.get(
                ctx.guild.categories, id=category_channel_id
            )
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(
                    read_messages=False
                ),
                ctx.author: discord.PermissionOverwrite(read_messages=True),
            }

            channel = await ctx.guild.create_text_channel(
                name=f"❌-{channel_name}",
                category=category_channel,
                overwrites=overwrites,
            )

            challenges.append(
                {
                    "id": id,
                    "name": name,
                    "category": category,
                    "channel_id": channel.id,
                    "solved": False,
                    "players": [],
                    "solvers": [],
                    "solve_time": None,
                    "solve_announcement": None,
                }
            )
            ctf_info["challenges"] = challenges

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": ctf_info},
                upsert=True,
            )
            # Announce that the challenge was added
            announcements_channel = discord.utils.get(
                ctx.guild.text_channels, id=ctf_info["announcement_channel_id"]
            )
            role = discord.utils.get(ctx.guild.roles, id=ctf_info["role_id"])

            embed = discord.Embed(
                title="🔔 New challenge created!",
                description=(
                    f"**Challenge name:** {name}\n"
                    f"**Category:** {category}\n\n"
                    f'Use `{self._bot.command_prefix}ctf workon "{name}"` to join.\n'
                    f"{role.mention}"
                ),
                colour=discord.Colour.dark_gold(),
            ).set_footer(text=datetime.strftime(datetime.now(), DATE_FORMAT))
            await announcements_channel.send(embed=embed)

            # Send challenge information in its respective channel if the challenge
            # was grabbed from CTFd after the `pull` command was invoked
            if name and category and description and value:
                tags = ", ".join(tags) or "No tags."
                files = [
                    f"{ctf_info['credentials']['url'].strip('/')}{file}"
                    for file in files
                ]
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
                message = await channel.send(embed=embed)
                await message.pin()
            else:
                await ctx.send("✅ Challenge created")

    @commands.guild_only()
    @in_ctf_channel()
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
        await ctx.defer()
        channel_id = ctx.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if challenge["channel_id"] != channel_id:
                continue

            challenge["name"] = new_name

            channel = discord.utils.get(ctx.guild.text_channels, id=channel_id)
            if new_category is not None:
                new_channel_name = sanitize_channel_name(f"{new_category}-{new_name}")
                challenge["category"] = new_category
            else:
                new_channel_name = sanitize_channel_name(
                    f"{channel.name.split('-')[0]}-{new_name}"
                )

            await channel.edit(name=new_channel_name)

            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )
            await ctx.send("✅ Challenge renamed")
            break

    @commands.guild_only()
    @in_ctf_channel()
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
        await ctx.defer()
        channel_id = ctx.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if not (challenge["name"] == name or challenge["channel_id"] == channel_id):
                continue

            channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel_id"]
            )
            await channel.delete()
            del challenges[idx]

            ctf_info["challenges"] = challenges

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )
            await ctx.send("✅ Challenge deleted")
            break

    @commands.guild_only()
    @in_ctf_channel()
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
        support1: Member = None,
        support2: Member = None,
        support3: Member = None,
        support4: Member = None,
    ) -> None:
        await ctx.defer()
        channel_id = ctx.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        solvers = [ctx.author.name] + [
            member.name for member in [support1, support2, support3, support4]
        ]

        for idx, challenge in enumerate(challenges):
            if challenge["channel_id"] != channel_id:
                continue

            # If the challenged was already solved
            if challenge["solved"]:
                await ctx.send("This challenge was already solved.")
                break

            challenge["solved"] = True
            challenge["solvers"] = solvers
            challenge["solve_time"] = datetime.now().strftime(DATE_FORMAT)

            channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel_id"]
            )

            try:
                await channel.edit(name=channel.name.replace("❌", "✅"))
            except Exception:
                # We've exceeded the 2 channel edit per 10 min set by Discord
                # should only happen during testing, or when the users are trolling
                # by spamming solve and unsolve.
                break

            solves_channel = self._bot.get_channel(ctf_info["solves_channel_id"])
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
            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )

            await ctx.solve("✅ Challenge solved")
            break
        # If we didn't find any challenge that corresponds to the channel from which
        # the command was run, then we're probably in a non-challenge channel.
        else:
            await ctx.send(
                "You may only run this command in the channel associated to the "
                "challenge."
            )

    @commands.guild_only()
    @in_ctf_channel()
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
        await ctx.defer()
        channel_id = ctx.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if challenge["channel_id"] != channel_id:
                continue

            if not challenge["solved"]:
                await ctx.send("This challenge is already marked as not solved.")
                break

            challenge["solved"] = False
            challenge["solvers"] = []
            challenge["solve_time"] = None

            channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel_id"]
            )

            try:
                await channel.edit(name=channel.name.replace("✅", "❌"))
            except Exception:
                # We've exceeded the 2 channel edit per 10 min set by Discord
                # should only happen during testing, or when the users are trolling
                # by spamming solve and unsolve.
                break

            # Delete the challenge solved announcement we made
            solves_channel = discord.utils.get(
                ctx.guild.text_channels, id=ctf_info["solves_channel_id"]
            )
            announcement = await solves_channel.fetch_message(
                challenge["solve_announcement"]
            )
            await announcement.delete()

            challenge["solve_announcement"] = None
            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )
            await ctx.send("✅ Challenge unsolved")
            break
        # If we didn't find any challenge that corresponds to the channel from which
        # the command was run, then we're probably in a non-challenge channel.
        else:
            await ctx.send(
                "You may only run this command in the channel associated to the "
                "challenge."
            )

    @commands.guild_only()
    @in_ctf_channel()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["workon"]["name"],
        description=cog_help["subcommands"]["workon"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["workon"]["options"]
        ],
    )
    async def _workon(self, ctx: SlashContext, name: str) -> None:
        await ctx.defer()
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if challenge["name"] != name:
                continue

            if challenge["solved"]:
                await ctx.send("You can't work on challenge that has been solved.")
                break

            if ctx.author.name not in challenge["players"]:
                challenge["players"].append(ctx.author.name)

            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel_id"]
            )

            await channel.set_permissions(ctx.author, read_messages=True)

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )

            await ctx.send("✅ Added to the challenge")
            await channel.send(f"{ctx.author.mention} wants to collaborate 🤝")
            break

    @commands.guild_only()
    @in_ctf_channel()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["unworkon"]["name"],
        description=cog_help["subcommands"]["unworkon"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["unworkon"]["options"]
        ],
    )
    async def _unworkon(self, ctx: SlashContext, name: str = None) -> None:
        await ctx.defer()
        channel_id = ctx.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if not (challenge["name"] == name or challenge["channel_id"] == channel_id):
                continue

            if ctx.author.name in challenge["players"]:
                challenge["players"].remove(ctx.author.name)

            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel_id"]
            )

            await channel.set_permissions(ctx.author, overwrite=None)

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )

            await ctx.send("✅ Removed from the challenge")
            await channel.send(
                f"{ctx.author.mention} left you alone, what a chicken! 🐥"
            )
            break

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
        await ctx.defer()
        category_channel_id = ctx.channel.category_id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": category_channel_id}
        )

        # CTF name wasn't provided, and we're outside a CTF category channel, so
        # we display statuses of all running CTFs.
        if ctf_info is None and name is None:
            ctfs = mongo[CTFS_COLLECTION].find({"archived": False})
        # CTF name wasn't provided, and we're inside a CTF category channel, so
        # we display status of the CTF related to this category channel.
        elif name is None:
            ctfs = [ctf_info]
        # CTF name was provided, and we're inside a CTF category channel, so
        # the priority here is for the provided CTF name.
        # - or -
        # CTF name was provided, and we're outside a CTF category channel, so
        # we display status of the requested CTF only.
        else:
            ctfs = mongo[CTFS_COLLECTION].find({"name": name, "archived": False})

        no_running_ctfs = True
        for ctf_info in ctfs:
            # Only display details about the CTF status if the command was run in
            # one of that CTF's channels
            if ctf_info["category_channel_id"] == category_channel_id:
                challenges = ctf_info["challenges"]
                if not challenges:
                    embed = discord.Embed(
                        title=f"{ctf_info['name']} status",
                        description="No challenges added yet.",
                        colour=discord.Colour.blue(),
                    )
                    await ctx.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title=f"{ctf_info['name']} status", colour=discord.Colour.blue()
                    )
                    for challenge in challenges:
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
                                    f"❌ {challenge['name']} ({challenge['category']})"
                                ),
                                value=workers,
                                inline=False,
                            )
                    await ctx.send(embed=embed)
            # Otherwise, let the user know that they should join the CTF first to
            # see the details.
            else:
                embed = discord.Embed(
                    title=f"{ctf_info['name']} status",
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
                await ctx.send("No running CTFs.")
            else:
                await ctx.send("No such CTF.")

    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    @in_ctf_channel()
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
        await ctx.defer()
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        if username is None or password is None or url is None:
            await ctx.send("Missing username, password or url.")
        else:
            ctf_info["credentials"]["url"] = url
            ctf_info["credentials"]["username"] = username
            ctf_info["credentials"]["password"] = password

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"credentials": ctf_info["credentials"]}},
            )

            channel = self._bot.get_channel(ctf_info["credentials"]["channel_id"])
            message = (
                "```yaml\n"
                f"CTF platform: {url}\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                "```"
            )

            await channel.purge()
            await channel.send(message)
            await ctx.send("✅ Credentials added")

            # Start a background task for this CTF in order to pull new challenges
            # periodically
            tasks.loop(minutes=5.0, reconnect=True)(self._periodic_puller).start(ctx)

    async def _periodic_puller(self, ctx: SlashContext) -> None:
        await self._pull.invoke(ctx)

    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    @in_ctf_channel()
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
        await ctx.defer()
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        url = ctf_info["credentials"]["url"]
        username = ctf_info["credentials"]["username"]
        password = ctf_info["credentials"]["password"]

        if username is None or password is None or url is None:
            await ctx.send("No credentials set for this CTF.")
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
    @commands.guild_only()
    @in_ctf_channel()
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
        # Don't defer if we already responded to the interaction, this happens when
        # `pull` is invoked by `addcreds`
        if not ctx.responded:
            await ctx.defer()

        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        url = ctfd_url or ctf_info["credentials"]["url"]
        username = ctf_info["credentials"]["username"]
        password = ctf_info["credentials"]["password"]

        if username is None or password is None or url is None:
            await ctx.send("No credentials set for this CTF.")
        else:
            for challenge in pull_challenges(url, username, password):
                await self._createchallenge.invoke(ctx, **challenge)

            if not ctx.responded:
                await ctx.send("✅ Done pulling challenges")

    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    @in_ctf_channel()
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
        self, ctx: SlashContext, note_type: str, note_format: str = None
    ) -> None:
        note_format = note_format or "embed"
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        for challenge in ctf_info["challenges"]:
            if challenge["channel_id"] == ctx.channel.id:
                break
        else:
            await ctx.send("❌ Not within a challenge channel")
            return

        notes_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctf_info["notes_channel_id"]
        )
        history = await ctx.channel.history(limit=2).flatten()
        message = history[-1].clean_content

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
                    description=message,
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
            await notes_channel.send(message)

    @commands.guild_only()
    @in_ctf_channel()
    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["submit"]["name"],
        description=cog_help["subcommands"]["submit"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["submit"]["options"]
        ],
    )
    async def _submit(
        self,
        ctx: SlashContext,
        flag: str,
        support1: Member = None,
        support2: Member = None,
        support3: Member = None,
        support4: Member = None,
    ) -> None:
        await ctx.defer()
        solvers = [ctx.author.name] + [
            member.name
            for member in [support1, support2, support3, support4]
            if member is not None
        ]

        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        ctfd_url = ctf_info["credentials"]["url"]
        username = ctf_info["credentials"]["username"]
        password = ctf_info["credentials"]["password"]
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if challenge["channel_id"] != ctx.channel.id:
                continue

            status, first_blood = submit_flag(
                ctfd_url, username, password, challenge["id"], flag
            )
            if status is None:
                await ctx.send("❌ Failed to submit the flag.")
            elif status == "correct":
                # Mark challenge as solved (as if `!ctf solve` was called)
                challenge["solved"] = True
                challenge["solvers"] = solvers
                challenge["solve_time"] = datetime.now().strftime(DATE_FORMAT)

                solves_channel = self._bot.get_channel(ctf_info["solves_channel_id"])

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

                channel = discord.utils.get(
                    ctx.guild.text_channels, id=challenge["channel_id"]
                )

                try:
                    await channel.edit(name=channel.name.replace("❌", "✅"))
                except Exception:
                    # We've exceeded the 2 channel edit per 10 min set by Discord, this
                    # should only happen during testing, or when the users are trolling
                    # by spamming solve and unsolve.
                    pass

                challenge["solve_announcement"] = announcement.id
                challenges[idx] = challenge
                ctf_info["challenges"] = challenges

                mongo[CTFS_COLLECTION].update(
                    {"_id": ctf_info["_id"]},
                    {"$set": {"challenges": ctf_info["challenges"]}},
                )
            elif status == "already_solved":
                await ctx.send("You already solved this challenge.")
            else:
                await ctx.send("❌ Incorrect flag.")
            break
        else:
            await ctx.send(
                "❌ This command may only be used from within a challenge channel."
            )


def setup(bot: Bot) -> None:
    bot.add_cog(CTF(bot))
