import os

import discord
from discord import app_commands

ASSETS = f"{os.path.dirname(__file__)}/assets"
PAGES = [
    {
        "title": "Introduction",
        "description": """\
Hello and welcome to the server!

This bot is used to manage CTFs within the Discord guild, monitor upcoming events, \
and more.
Be sure to learn the basics of its usage to collaborate effectively with the team 💪

If you find this bot helpful, please ⭐ its [GitHub repository]\
(https://github.com/hfz1337/Eruditus)!
""",
        "image": None,
    },
    {
        "title": "CTFtime Events Tracking",
        "description": """\
The bot periodically checks for events added to the [CTFtime](https://ctftime.org/) \
website.
If a CTF is starting in no more than 7 days, a Discord scheduled event is created in \
the Discord guild (see the top left corner).
""",
        "image": discord.File(f"{ASSETS}/1.png"),
    },
    {
        "title": "Before a CTF",
        "description": """\
One hour before a CTF starts, the bot performs the following actions:
- Creates a category channel specifically for that CTF, along with a special role.
- Automatically grants access to the CTF channels to all members who marked \
themselves `Interested` in that CTF.
- Attempts auto-registration on the CTF platform (currently supports only CTFd and \
rCTF).

Admins can also manually create the CTF using `/ctf createctf`.

If you forgot to click `Interested`, you can still join a CTF using `/ctf join` \
(note the autocompletion).
""",
        "image": discord.File(f"{ASSETS}/2.png"),
    },
    {
        "title": "During a CTF",
        "description": """\
A final reminder is sent in the `general` channel when the CTF begins.

The bot creates the following channels:
- 🤖-bot-cmds: for executing bot commands (to avoid spamming other channels).
- 🔑-credentials: contains login credentials for the CTF platform.
- 📝-notes: for communicating challenge progress to other members (use `Apps > Take \
note` from a message context menu).
- 📣-announcements: announces new challenges from the CTF platform. Notes:
  - The bot checks for new challenges every 2 minutes (default).
  - Use `/ctf pull` to force fetch challenges.
  - Challenge announcements include a button to join the challenge (alternatively, \
use `/ctf workon`).
- 🎉-solves: announces solved challenges. Note:
  - Use `/ctf submit` for flag submissions, enabling the bot to track first bloods \
and format announcements accordingly 🩸
  - If you forget to submit a flag through the bot, you can use `/ctf solve`.
  - For both of the above commands, you can use the optional `members` parameter to \
tag people who contributed to solving the challenge (use `@`).
- 📈-scoreboard: periodically updated with the latest scores.

Additionally, the bot creates a channel for each CTF category, with each challenge \
having its own thread in the respective category channel.

When the emoji in a CTF category channel's name changes from 🔄 to 🎯, it indicates \
that the category is maxed out.

The bot offers useful utilities like `/search` and `/revshell`. Use `/help` for more \
information.
""",
        "image": discord.File(f"{ASSETS}/3.png"),
    },
    {
        "title": "After the CTF",
        "description": """\
After the CTF concludes, a summary is posted in the scoreboard channel, and a message \
is sent in the general channel to notify members that the CTF has ended.
""",
        "image": None,
    },
]


class Paginator(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.current_page = 0
        self.add_item(
            discord.ui.Button(
                label="<<",
                style=discord.ButtonStyle.gray,
                disabled=True,
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Back", style=discord.ButtonStyle.blurple, disabled=True
            )
        )
        self.add_item(
            discord.ui.Button(label="Next", style=discord.ButtonStyle.blurple)
        )
        self.add_item(
            discord.ui.Button(
                label=">>",
                style=discord.ButtonStyle.gray,
            )
        )
        self.add_item(discord.ui.Button(label="Quit", style=discord.ButtonStyle.red))
        self.children[0].callback = self.backward_button_callback
        self.children[1].callback = self.back_button_callback
        self.children[2].callback = self.next_button_callback
        self.children[3].callback = self.forward_button_callback
        self.children[4].callback = self.quit_button_callback

    async def update_message(self, interaction: discord.Interaction) -> None:
        attachments = []
        embed = discord.Embed(
            color=discord.Color.light_gray(),
            title=PAGES[self.current_page]["title"],
            description=PAGES[self.current_page]["description"],
        )
        if PAGES[self.current_page]["image"] is not None:
            embed.set_image(
                url=f"attachment://{PAGES[self.current_page]['image'].filename}"
            )
            attachments = [PAGES[self.current_page]["image"]]

        await interaction.response.edit_message(
            embed=embed,
            view=self,
            attachments=attachments,
        )

    async def backward_button_callback(self, interaction: discord.Interaction) -> None:
        self.current_page = 0
        self.children[0].disabled = True
        self.children[1].disabled = True
        self.children[2].disabled = False
        self.children[3].disabled = False
        await self.update_message(interaction)

    async def forward_button_callback(self, interaction: discord.Interaction) -> None:
        self.current_page = len(PAGES) - 1
        self.children[0].disabled = False
        self.children[1].disabled = False
        self.children[2].disabled = True
        self.children[3].disabled = True
        await self.update_message(interaction)

    async def back_button_callback(self, interaction: discord.Interaction) -> None:
        self.current_page -= 1
        self.children[2].disabled = False
        self.children[3].disabled = False
        if self.current_page == 0:
            self.children[0].disabled = True
            self.children[1].disabled = True
        await self.update_message(interaction)

    async def next_button_callback(self, interaction: discord.Interaction) -> None:
        self.current_page += 1
        self.children[0].disabled = False
        self.children[1].disabled = False
        if self.current_page == len(PAGES) - 1:
            self.children[2].disabled = True
            self.children[3].disabled = True
        await self.update_message(interaction)

    async def quit_button_callback(self, interaction: discord.Interaction) -> None:
        await interaction.message.delete()


class Intro(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="intro",
            description="Show bot instructions for newcomers.",
            callback=self.cmd_callback,  # type: ignore
        )

    async def cmd_callback(self, interaction: discord.Interaction) -> None:
        """Show bot instructions for newcomers.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.send_message(
            embed=discord.Embed(
                color=discord.Color.light_gray(),
                title=PAGES[0]["title"],
                description=PAGES[0]["description"],
            ),
            view=Paginator(),
        )
