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

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctf["credentials"]["url"] = self.url

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
                ctf["credentials"]["invite"] = self.invite.value
                ctf["credentials"]["teamToken"] = team_token
                message = (
                    f"rCTF platform: {self.url}\n"
                    f"Invite link: {self.invite.value}\n"
                    "```yaml\n"
                    f"Team token: {team_token}\n"
                    "```"
                )

            case Platform.CTFd:
                ctf["credentials"]["username"] = self.username.value
                ctf["credentials"]["password"] = self.password.value
                message = (
                    f"CTFd platform: {self.url}\n"
                    "```yaml\n"
                    f"Username: {self.username.value}\n"
                    f"Password: {self.password.value}\n"
                    "```"
                )
            case _:
                ctf["credentials"]["username"] = self.username.value
                ctf["credentials"]["password"] = self.password.value
                ctf["credentials"]["invite"] = self.invite.value
                ctf["credentials"]["teamToken"] = self.token.value
                # fmt: off
                message = (
                    f"CTF platfrom: {self.url}\n"
                    f"Invite link: {self.invite.value}\n" if self.invite.value else ""
                    "```yaml\n"
                    f"Username: {self.username.value}\n"
                    f"Password: {self.password.value}\n" if self.password.value else ""
                    f"Token: {self.token.value}\n" if self.token.value else ""
                    "```"
                )
                # fmt: on

        ctf["credentials"]["message"] = message
        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]},
            {"$set": {"credentials": ctf["credentials"]}},
        )

        creds_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
        )

        await creds_channel.purge()
        await creds_channel.send(message, suppress_embeds=True)
        await interaction.followup.send("✅ Credentials added.", ephemeral=True)
