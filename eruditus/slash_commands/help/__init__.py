import discord
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
                    "during CTF competitions."
                ),
                colour=discord.Colour.blue(),
            )
            .set_thumbnail(url=interaction.client.user.display_avatar.url)
            .set_footer(
                text=(
                    "“I never desire to converse with a man who has written more than "
                    "he has read.”\n"
                    "― Samuel Johnson, Johnsonian Miscellanies - Vol II"
                )
            )
        )

        for command in interaction.client.tree.get_commands():
            embed.add_field(
                name=f"/{command.name}",
                value=command.description,
                inline=False,
            )

        await interaction.response.send_message(embed=embed)
