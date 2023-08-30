import discord
from config import COMMIT_HASH, GUILD_ID
from discord import app_commands


class Help(app_commands.Command):
    def __init__(self) -> None:
        super().__init__(
            name="help",
            description="Show help about the bot usage.",
            callback=self.callback,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Show help about the bot usage."""
        embed = (
            discord.Embed(
                title="Eruditus - CTF helper bot",
                url="https://github.com/hfz1337/Eruditus",
                description=(
                    "Eruditus is dedicated to CTF teams who communicate via Discord "
                    "during CTF competitions.\n"
                    f"Current revision: [`{COMMIT_HASH:.8}`]"
                    f"(https://github.com/hfz1337/Eruditus/commit/{COMMIT_HASH})."
                ),
                colour=discord.Colour.blue(),
            )
            .set_thumbnail(url=interaction.client.user.display_avatar.url)
            .set_footer(text="Made with ❤️ by hfz.")
        )

        # Show help for global commands.
        for command in interaction.client.tree.get_commands():
            # Skip context menu commands.
            if command.__class__.__bases__[0] == discord.app_commands.ContextMenu:
                continue

            embed.add_field(
                name=f"/{command.name}",
                value=command.description,
                inline=False,
            )

        # If the command was invoked from within the guild, we also show guild
        # specific commands.
        if interaction.guild:
            for command in interaction.client.tree.get_commands(
                guild=discord.Object(id=GUILD_ID)
            ):
                # Skip context menu commands.
                if command.__class__.__bases__[0] == discord.app_commands.ContextMenu:
                    continue

                embed.add_field(
                    name=f"/{command.name}",
                    value=command.description,
                    inline=False,
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)
