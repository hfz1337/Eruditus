from urllib.parse import parse_qs, urlparse

import discord

from config import CTF_COLLECTION, DBNAME, MONGO
from lib.platforms import Platform, PlatformABC


class CredentialsForm(discord.ui.Modal, title="Add CTF credentials"):
    def __init__(self, url: str, platform: PlatformABC, **kwargs) -> None:
        super().__init__()
        self.url = url
        self.platform = platform
        for key in kwargs:
            setattr(self, key, discord.ui.TextInput(**kwargs[key]))
            self.add_item(getattr(self, key))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        match Platform(self.platform):
            case Platform.RCTF:
                parsed_url = urlparse(self.invite.value)
                params = parse_qs(parsed_url.query)
                if not (team_token := params.get("token")):
                    await interaction.followup.send(
                        (
                            "Token was not found in the URL, please submit a valid "
                            "invite link."
                        ),
                        ephemeral=True,
                    )
                    return
                team_token = team_token[0]

                credentials = {
                    "url": self.url,
                    "teamToken": team_token,
                    "invite": self.invite.value,
                    "_message": (
                        f"rCTF platform: {self.url}\n"
                        f"Invite link: {self.invite.value}\n"
                        "```yaml\n"
                        f"Team token: {team_token}\n"
                        "```"
                    ),
                }

            case Platform.CTFd:
                credentials = {
                    "url": self.url,
                    "username": self.username.value,
                    "password": self.password.value,
                    "_message": (
                        f"CTFd platform: {self.url}\n"
                        "```yaml\n"
                        f"Username: {self.username.value}\n"
                        f"Password: {self.password.value}\n"
                        "```"
                    ),
                }
            case _:
                lines = [
                    f"CTF platfrom: {self.url}",
                    f"Invite link: {self.invite.value}" if self.invite.value else None,
                    "```yaml",
                    f"Username: {self.username.value}",
                    f"Password: {self.password.value}" if self.password.value else None,
                    f"Token: {self.token.value}" if self.token.value else None,
                    "```",
                ]
                credentials = {
                    "url": self.url,
                    "username": self.username.value,
                    "password": self.password.value,
                    "invite": self.invite.value,
                    "teamToken": self.token.value,
                    "_message": "\n".join(line for line in lines if line is not None),
                }

        # Add credentials.
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]},
            {"$set": {"credentials": credentials}},
        )

        creds_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
        )
        await creds_channel.purge()
        await creds_channel.send(credentials["_message"], suppress_embeds=True)
        await interaction.followup.send("✅ Credentials added.", ephemeral=True)
