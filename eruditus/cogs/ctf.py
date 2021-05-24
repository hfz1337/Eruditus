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

from discord_slash.model import SlashCommandOptionType as OptionType
from discord_slash.utils.manage_commands import create_option
from typing import Union, Tuple, Generator, List
from discord_slash import SlashContext, cog_ext
from discord.ext.commands import Context, Bot
from string import ascii_lowercase, digits
from discord.ext import tasks, commands
from pymongo import MongoClient
from bs4 import BeautifulSoup
from datetime import datetime
from discord import Member
from help import help_info
from hashlib import md5
import requests
import discord
import os
import re

# Load environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
CTFTIME_EVENTS_COLLECTION = os.getenv("CTFTIME_EVENTS_COLLECTION")
CTFS_COLLECTION = os.getenv("CTFS_COLLECTION")
ARCHIVE_CATEGORY_CHANNEL = os.getenv("ARCHIVE_CATEGORY_CHANNEL")
DBNAME = os.getenv("DBNAME")
GUILD_ID = int(os.getenv("GUILD_ID"))

# Date format used when announcing challenge solves
DATE_FORMAT = "%a, %d %B %Y, %H:%M UTC"

# MongoDB handle
mongo = MongoClient(MONGODB_URI)[DBNAME]


def sanitize_channel_name(name: str) -> str:
    whitelist = ascii_lowercase + digits + "-_"
    name = name.lower().replace(" ", "-")

    for char in name:
        if char not in whitelist:
            name = name.replace(char, "")

    while "--" in name:
        name = name.replace("--", "-")

    return name


def derive_colour(string: str) -> int:
    return int(md5(string.encode()).hexdigest()[:6], 16)


def is_ctfd_platform(ctfd_base_url: str) -> bool:
    ctfd_signature = "Powered by CTFd"
    response = requests.get(url=f"{ctfd_base_url.strip()}/")
    return ctfd_signature in response.text


def ctfd_login(ctfd_base_url: str, username: str, password: str) -> dict:
    ctfd_base_url = ctfd_base_url.strip("/")

    # Confirm that we're dealing with a CTFd platform
    if not is_ctfd_platform(ctfd_base_url):
        return None

    # Get the nonce
    response = requests.get(url=f"{ctfd_base_url}/login")
    cookies = response.cookies.get_dict()
    nonce = BeautifulSoup(response.content, "html.parser").find(
        "input", {"id": "nonce"}
    )["value"]

    # Login to CTFd
    data = {"name": username, "password": password, "_submit": "Submit", "nonce": nonce}
    response = requests.post(
        url=f"{ctfd_base_url}/login", data=data, cookies=cookies, allow_redirects=False
    )
    return response.cookies.get_dict()


def ctfd_submit_flag(
    ctfd_base_url: str, username: str, password: str, challenge_id: int, flag: str
) -> Tuple[str, bool]:
    """Attempts to submit the flag into the CTFd platform and checks if we got first
    blood in case it succeeds.

    :Return:
        a tuple containing the status message and a boolean indicating if we got
        first blood.
    """
    ctfd_base_url = ctfd_base_url.strip("/")
    cookies = ctfd_login(ctfd_base_url, username, password)
    if cookies is None:
        return (None, None)

    # Get CSRF token
    response = requests.get(url=f"{ctfd_base_url}/challenges", cookies=cookies)
    csrf_nonce = re.search('(?<=csrfNonce\': ")[A-Fa-f0-9]+(?=")', response.text)
    if csrf_nonce is None:
        return (None, None)

    csrf_nonce = csrf_nonce.group(0)
    json = {"challenge_id": challenge_id, "submission": flag}
    response = requests.post(
        url=f"{ctfd_base_url}/api/v1/challenges/attempt",
        json=json,
        cookies=cookies,
        headers={"CSRF-Token": csrf_nonce},
    )
    # Check if we got a response
    if response.status_code == 200 and response.json()["success"]:
        # The flag was correct
        if response.json()["data"]["status"] == "correct":
            # Check if we got first blood
            response = requests.get(
                url=f"{ctfd_base_url}/api/v1/challenges/{challenge_id}",
                cookies=cookies,
                allow_redirects=False,
            )
            if response.status_code == 200 and response.json()["success"]:
                return ("correct", response.json()["data"]["solves"] == 1)
            else:
                return ("correct", None)
        # We already solved this challenge
        elif response.json()["data"]["status"] == "already_solved":
            return ("already_solved", None)
        # The flag was incorrect
        else:
            return ("incorrect", None)
    else:
        return (None, None)


def pull_ctfd_challenges(
    ctfd_base_url: str, username: str, password: str
) -> Generator[dict, None, None]:
    ctfd_base_url = ctfd_base_url.strip("/")

    # Confirm that we're dealing with a CTFd platform
    if not is_ctfd_platform(ctfd_base_url):
        return None

    # Maybe the challenges endpoint is accessible to the public?
    response = requests.get(
        url=f"{ctfd_base_url}/api/v1/challenges", allow_redirects=False
    )

    if response.status_code != 200:
        # Perhaps the API access needs authentication, so we login to the CTFd platform.
        cookies = ctfd_login(ctfd_base_url, username, password)

        # Get challenges
        response = requests.get(
            url=f"{ctfd_base_url}/api/v1/challenges",
            cookies=cookies,
            allow_redirects=False,
        )

    if response.status_code == 200 and response.json()["success"]:
        # Loop through the challenges and get information about each challenge by
        # requesting the `/api/v1/challenges/{challenge_id}` endpoint
        for challenge_id in [
            challenge["id"]
            for challenge in response.json()["data"]
            if not challenge["solved_by_me"]
        ]:
            response = requests.get(
                url=f"{ctfd_base_url}/api/v1/challenges/{challenge_id}",
                cookies=cookies,
                allow_redirects=False,
            )
            if response.status_code == 200 and response.json()["success"]:
                challenge = response.json()["data"]
                yield {
                    "id": challenge["id"],
                    "name": challenge["name"],
                    "value": challenge["value"],
                    "description": challenge["description"],
                    "category": challenge["category"],
                    "tags": challenge["tags"],
                    "files": challenge["files"],
                }


def in_ctf_channel() -> bool:
    async def predicate(ctx: Context) -> bool:
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        if ctf_info:
            return True
        else:
            await ctx.send("You must be in a created CTF channel to use this command.")
            return False

    return commands.check(predicate)


class CTF(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.pull_new_challenges.start()

    @commands.group()
    @commands.guild_only()
    async def ctf(self, ctx: Context) -> None:
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"Commands group for {self.bot.command_prefix}{ctx.invoked_with}",
                colour=discord.Colour.blue(),
            ).set_thumbnail(url=f"{self.bot.user.avatar_url}")

            for command in help_info[ctx.invoked_with]:
                embed.add_field(
                    name=help_info[ctx.invoked_with][command]["usage"].format(
                        self.bot.command_prefix
                    ),
                    value=help_info[ctx.invoked_with][command]["brief"],
                    inline=False,
                )

            await ctx.send(embed=embed)

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
    @ctf.command(aliases=help_info["ctf"]["createctf"]["aliases"])
    async def createctf(self, ctx: Context, ctf_name: str) -> None:
        role = discord.utils.get(ctx.guild.roles, name=ctf_name)
        if role is None:
            role = await ctx.guild.create_role(
                name=ctf_name,
                colour=derive_colour(ctf_name),
                mentionable=True,
            )

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True),
        }

        category_channel = discord.utils.get(ctx.guild.categories, name=ctf_name)
        if category_channel is None:
            # If the command was invoked by us, then the CTF probably didn't start yet,
            # the emoji will be set to a clock, and once the CTF starts it will be
            # change by a red dot.
            emoji = "⏰" if ctx.author.id == self.bot.user.id else "🔴"
            category_channel = await ctx.guild.create_category(
                name=f"{emoji} {ctf_name}",
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
            "name": ctf_name,
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
        # If the command was called by us, don't add the reaction
        if ctx.message.author.id != self.bot.user.id:
            await ctx.message.add_reaction("✅")

    @commands.bot_has_permissions(manage_channels=True)
    @commands.has_permissions(manage_channels=True)
    @ctf.command(aliases=help_info["ctf"]["renamectf"]["aliases"])
    @in_ctf_channel()
    async def renamectf(self, ctx: Context, new_ctf_name: str) -> None:
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        old_name = ctf_info["name"]
        ctf_info["name"] = new_ctf_name

        category_channel = discord.utils.get(
            ctx.guild.categories, id=ctf_info["category_channel_id"]
        )

        await category_channel.edit(
            name=category_channel.name.replace(old_name, new_ctf_name)
        )

        mongo[CTFS_COLLECTION].update(
            {"_id": ctf_info["_id"]}, {"$set": {"name": ctf_info["name"]}}
        )
        await ctx.message.add_reaction("✅")

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
    @ctf.command(aliases=help_info["ctf"]["archivectf"]["aliases"])
    async def archivectf(
        self, ctx: Context, mode: str = "minimal", ctf_name: str = None
    ):
        if not (mode == "minimal" or mode == "all"):
            await ctx.send("Archiving mode can either be **minimal** or **all**.")
            return

        if ctf_name is None:
            ctf_info = mongo[CTFS_COLLECTION].find_one(
                {"category_channel_id": ctx.channel.category_id}
            )
        else:
            ctf_info = mongo[CTFS_COLLECTION].find_one({"name": ctf_name})

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
                                "archive_category_channel_id": archive_category_channel.id
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
            await ctx.message.add_reaction("✅")
        else:
            await ctx.send("No such CTF.")

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_permissions(manage_channels=True)
    @ctf.command(aliases=help_info["ctf"]["deletectf"]["aliases"])
    async def deletectf(self, ctx: Context, ctf_name: str = None) -> None:
        if ctf_name is None:
            ctf_info = mongo[CTFS_COLLECTION].find_one(
                {"category_channel_id": ctx.channel.category_id}
            )
        else:
            ctf_info = mongo[CTFS_COLLECTION].find_one({"name": ctf_name})

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
            await ctx.message.add_reaction("✅")
        else:
            await ctx.send("No such CTF.")

    @commands.bot_has_permissions(manage_roles=True)
    @ctf.command(aliases=help_info["ctf"]["join"]["aliases"])
    async def join(self, ctx: Context, ctf_name: str) -> None:
        role = discord.utils.get(ctx.guild.roles, name=ctf_name)

        if role is None:
            await ctx.send("No such CTF.")
        else:
            await ctx.message.author.add_roles(role)

            # Announce that the user joined the CTF
            ctf_info = mongo[CTFS_COLLECTION].find_one({"role_id": role.id})
            if not ctf_info:
                return

            ctf_general_channel = discord.utils.get(
                ctx.guild.text_channels,
                category_id=ctf_info["category_channel_id"],
                name="general",
            )
            await ctx.message.add_reaction("✅")
            await ctf_general_channel.send(
                f"{ctx.message.author.mention} joined the battle ⚔️"
            )

    @commands.bot_has_permissions(manage_roles=True)
    @ctf.command(aliases=help_info["ctf"]["leave"]["aliases"])
    @in_ctf_channel()
    async def leave(self, ctx: Context) -> None:
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        role = discord.utils.get(ctx.guild.roles, id=ctf_info["role_id"])
        await ctx.message.author.remove_roles(role)

        # Announce that the user left the CTF
        ctf_info = mongo[CTFS_COLLECTION].find_one({"role_id": role.id})
        if not ctf_info:
            return

        ctf_general_channel = discord.utils.get(
            ctx.guild.text_channels,
            category_id=ctf_info["category_channel_id"],
            name="general",
        )
        await ctx.message.add_reaction("✅")
        await ctf_general_channel.send(
            f"{ctx.message.author.mention} abandonned the boat :frowning:"
        )

    @ctf.command(aliases=help_info["ctf"]["createchallenge"]["aliases"])
    @in_ctf_channel()
    async def createchallenge(
        self,
        ctx: Context,
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
                ctx.message.author: discord.PermissionOverwrite(read_messages=True),
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
                    f'Use `{self.bot.command_prefix}ctf workon "{name}"` to join.\n'
                    f"{role.mention}"
                ),
                colour=discord.Colour.dark_gold(),
            ).set_footer(text=datetime.strftime(datetime.now(), DATE_FORMAT))
            await announcements_channel.send(embed=embed)

            # Send challenge information in its respective channel if the challenge
            # was grabbed from CTFd
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

            # If the command was called by us, don't add the reaction
            if ctx.message.author.id != self.bot.user.id:
                await ctx.message.add_reaction("✅")

    @ctf.command(aliases=help_info["ctf"]["renamechallenge"]["aliases"])
    @in_ctf_channel()
    async def renamechallenge(
        self, ctx: Context, new_challenge_name: str, new_category_name: str = None
    ) -> None:
        channel_id = ctx.message.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if challenge["channel_id"] != channel_id:
                continue

            challenge["name"] = new_challenge_name

            channel = discord.utils.get(ctx.guild.text_channels, id=channel_id)
            if new_category_name is not None:
                new_channel_name = sanitize_channel_name(
                    f"{new_category_name}-{new_challenge_name}"
                )
                challenge["category"] = new_category_name
            else:
                new_channel_name = sanitize_channel_name(
                    f"{channel.name.split('-')[0]}-{new_challenge_name}"
                )

            await channel.edit(name=new_channel_name)

            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )
            await ctx.message.add_reaction("✅")
            break

    @ctf.command(aliases=help_info["ctf"]["deletechallenge"]["aliases"])
    @in_ctf_channel()
    async def deletechallenge(self, ctx: Context, name: str = None) -> None:
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
            await ctx.message.add_reaction("✅")
            break

    @ctf.command(aliases=help_info["ctf"]["solve"]["aliases"])
    @in_ctf_channel()
    async def solve(self, ctx: Context, *solvers: Union[Member, str]) -> None:
        channel_id = ctx.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        solvers = [ctx.message.author.name] + [
            member.name if isinstance(member, Member) else member for member in solvers
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
                break

            solves_channel = self.bot.get_channel(ctf_info["solves_channel_id"])
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

            await ctx.message.add_reaction("✅")
            break
        # If we didn't find any challenge that corresponds to the channel from which
        # the command was run, then we're probably in a non-challenge channel.
        else:
            await ctx.send(
                "You may only run this command in the channel associated to the challenge."
            )

    @ctf.command(aliases=help_info["ctf"]["unsolve"]["aliases"])
    @in_ctf_channel()
    async def unsolve(self, ctx: Context) -> None:
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
            await ctx.message.add_reaction("✅")
            break
        # If we didn't find any challenge that corresponds to the channel from which
        # the command was run, then we're probably in a non-challenge channel.
        else:
            await ctx.send(
                "You may only run this command in the channel associated to the challenge."
            )

    @ctf.command(aliases=help_info["ctf"]["workon"]["aliases"])
    @in_ctf_channel()
    async def workon(self, ctx: Context, name: str) -> None:
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

            if ctx.message.author.name not in challenge["players"]:
                challenge["players"].append(ctx.message.author.name)

            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel_id"]
            )

            await channel.set_permissions(ctx.message.author, read_messages=True)

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )

            await ctx.message.add_reaction("✅")
            await channel.send(f"{ctx.message.author.mention} wants to collaborate 🤝")
            break

    @ctf.command(aliases=help_info["ctf"]["unworkon"]["aliases"])
    @in_ctf_channel()
    async def unworkon(self, ctx: Context, name: str = None) -> None:
        channel_id = ctx.channel.id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        challenges = ctf_info["challenges"]

        for idx, challenge in enumerate(challenges):
            if not (challenge["name"] == name or challenge["channel_id"] == channel_id):
                continue

            if ctx.message.author.name in challenge["players"]:
                challenge["players"].remove(ctx.message.author.name)

            challenges[idx] = challenge
            ctf_info["challenges"] = challenges

            channel = discord.utils.get(
                ctx.guild.text_channels, id=challenge["channel_id"]
            )

            await channel.set_permissions(ctx.message.author, overwrite=None)

            mongo[CTFS_COLLECTION].update(
                {"_id": ctf_info["_id"]},
                {"$set": {"challenges": ctf_info["challenges"]}},
            )

            await ctx.message.add_reaction("✅")
            await channel.send(
                f"{ctx.message.author.mention} left you alone, what a chicken! 🐥"
            )
            break

    @ctf.command(aliases=help_info["ctf"]["status"]["aliases"])
    async def status(self, ctx: Context, ctf_name: str = None) -> None:
        category_channel_id = ctx.channel.category_id
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": category_channel_id}
        )

        # CTF name wasn't provided, and we're outside a CTF category channel, so
        # we display statuses of all running CTFs.
        if ctf_info is None and ctf_name is None:
            ctfs = mongo[CTFS_COLLECTION].find({"archived": False})
        # CTF name wasn't provided, and we're inside a CTF category channel, so
        # we display status of the CTF related to this category channel.
        elif ctf_name is None:
            ctfs = [ctf_info]
        # CTF name was provided, and we're inside a CTF category channel, so
        # the priority here is for the provided CTF name.
        # - or -
        # CTF name was provided, and we're outside a CTF category channel, so
        # we display status of the requested CTF only.
        else:
            ctfs = mongo[CTFS_COLLECTION].find({"name": ctf_name, "archived": False})

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
                                name=f"✅ {challenge['name']} ({challenge['category']})",
                                value=(
                                    "```diff\n"
                                    f"+ Solver{['', 's'][len(challenge['solvers']) > 1]}: "
                                    f"{', '.join(challenge['solvers']).strip()}\n"
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
                                    f"! Worker{['', 's'][len(challenge['players']) > 1]}: "
                                    f"{', '.join(challenge['players']).strip()}\n"
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
            if ctf_name is None:
                await ctx.send("No running CTFs.")
            else:
                await ctx.send("No such CTF.")

    @commands.bot_has_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @ctf.command(aliases=help_info["ctf"]["addcreds"]["aliases"])
    @in_ctf_channel()
    async def addcreds(
        self, ctx: Context, username: str, password: str, url: str
    ) -> None:
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

            channel = self.bot.get_channel(ctf_info["credentials"]["channel_id"])
            message = (
                "```yaml\n"
                f"CTF platform: {url}\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                "```"
            )

            await channel.purge()
            await channel.send(message)
            await ctx.message.add_reaction("✅")

            # Try to pull challenges
            await ctx.invoke(self.bot.get_command("ctf pull"))

    @commands.bot_has_permissions(manage_messages=True)
    @ctf.command(aliases=help_info["ctf"]["showcreds"]["aliases"])
    @in_ctf_channel()
    async def showcreds(self, ctx: Context) -> None:
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
    @commands.has_permissions(manage_messages=True)
    @ctf.command(aliases=help_info["ctf"]["pull"]["aliases"])
    @in_ctf_channel()
    async def pull(self, ctx: Context, ctfd_url: str = None) -> None:
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        url = ctfd_url or ctf_info["credentials"]["url"]
        username = ctf_info["credentials"]["username"]
        password = ctf_info["credentials"]["password"]

        if username is None or password is None or url is None:
            await ctx.send("No credentials set for this CTF.")
        else:
            for challenge in pull_ctfd_challenges(url, username, password):
                await ctx.invoke(
                    self.bot.get_command("ctf createchallenge"), **challenge
                )

            # If the command was called by us, don't add the reaction
            if ctx.message.author.id != self.bot.user.id:
                await ctx.message.add_reaction("✅")

    @commands.bot_has_permissions(manage_messages=True)
    @ctf.command(aliases=help_info["ctf"]["takenote"]["aliases"])
    @in_ctf_channel()
    async def takenote(
        self, ctx: Context, note_type: str, note_format: str = None
    ) -> None:
        note_format = note_format or "embed"
        ctf_info = mongo[CTFS_COLLECTION].find_one(
            {"category_channel_id": ctx.channel.category_id}
        )
        for challenge in ctf_info["challenges"]:
            if challenge["channel_id"] == ctx.channel.id:
                break
        else:
            challenge = None

        notes_channel = discord.utils.get(
            ctx.guild.text_channels, id=ctf_info["notes_channel_id"]
        )
        history = await ctx.channel.history(limit=2).flatten()
        message = history[-1].clean_content

        title = None
        if note_type == "progress" and challenge is not None:
            title = f"🔄 **Challenge progress - {challenge['name']} ({challenge['category']})**"
            colour = discord.Colour.red()
        elif note_type in ["info", "note"]:
            title = "📝 **Note**"
            colour = discord.Colour.green()

        if title is not None:
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
                await ctx.message.add_reaction("✅")

            elif note_format == "raw":
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
                await ctx.message.add_reaction("✅")
            else:
                await ctx.message.add_reaction("❌")
        else:
            await ctx.message.add_reaction("❌")

    @tasks.loop(minutes=5.0, reconnect=True)
    async def pull_new_challenges(self) -> None:
        # Wait until the bot's internal cache is ready
        await self.bot.wait_until_ready()

        for ctf_info in mongo[CTFS_COLLECTION].find({"archived": False}):
            url = ctf_info["credentials"]["url"]
            username = ctf_info["credentials"]["username"]
            password = ctf_info["credentials"]["password"]

            if username and password and url:
                # Get the credentials channels
                credentials_channel = discord.utils.get(
                    self.bot.guilds[0].text_channels,
                    id=ctf_info["credentials"]["channel_id"],
                )
                if not credentials_channel:
                    continue
                # Get the credentials message from that channel
                history = await credentials_channel.history(limit=1).flatten()
                # Get the context from that message
                ctx = await self.bot.get_context(history[0])

                await ctx.invoke(self.bot.get_command("ctf pull"))

    @cog_ext.cog_slash(
        description="Submit flag to CTFd",
        guild_ids=[GUILD_ID],
        options=[
            create_option(
                name="flag",
                description="Flag of the challenge",
                option_type=OptionType.STRING,
                required=True,
            ),
            # Discord Slash commands don't allow variadic arguments yet
            create_option(
                name="support1",
                description="Member who helped solving the challenge",
                option_type=OptionType.USER,
                required=False,
            ),
            create_option(
                name="support2",
                description="Member who helped solving the challenge",
                option_type=OptionType.USER,
                required=False,
            ),
            create_option(
                name="support3",
                description="Member who helped solving the challenge",
                option_type=OptionType.USER,
                required=False,
            ),
            create_option(
                name="support4",
                description="Member who helped solving the challenge",
                option_type=OptionType.USER,
                required=False,
            ),
        ],
    )
    @in_ctf_channel()
    async def submit(
        self,
        ctx: SlashContext,
        flag: str,
        support1: Member = None,
        support2: Member = None,
        support3: Member = None,
        support4: Member = None,
    ) -> None:
        # Defer the response because it will take time to submit the flag
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

            status, first_blood = ctfd_submit_flag(
                ctfd_url, username, password, challenge["id"], flag
            )
            if status is None:
                await ctx.send("❌ Failed to submit the flag.")
            elif status == "correct":
                # Mark challenge as solved (as if `!ctf solve` was called)
                challenge["solved"] = True
                challenge["solvers"] = solvers
                challenge["solve_time"] = datetime.now().strftime(DATE_FORMAT)

                solves_channel = self.bot.get_channel(ctf_info["solves_channel_id"])

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
                    # We've exceeded the 2 channel edit per 10 min set by Discord
                    break

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
