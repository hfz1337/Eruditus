from urllib.parse import urlencode

import discord

from config import CTF_COLLECTION, DBNAME, MONGO
from lib.platforms import Platform, PlatformABC, PlatformCTX


class RegistrationForm(discord.ui.Modal, title="Register to the CTF"):
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
                ctx: PlatformCTX = PlatformCTX(
                    base_url=self.url,
                    args={"team": self.team.value, "email": self.email.value},
                )
                result = await self.platform.register(ctx)
                if not result.success:
                    await interaction.followup.send(result.message)
                    return

                invite_url = f"{ctx.url_stripped}/login?" + urlencode(
                    {"token": result.invite}
                )
                credentials = {
                    "url": self.url,
                    "team": self.team.value,
                    "email": self.email.value,
                    "teamToken": result.invite,
                    "invite": invite_url,
                    "_message": (
                        f"rCTF platform: {self.url}\n"
                        f"Invite link: {invite_url}\n"
                        "```yaml\n"
                        f"Team token: {result.invite}\n"
                        "```"
                    ),
                }

            case Platform.CTFd:
                ctx: PlatformCTX = PlatformCTX(
                    base_url=self.url,
                    args={
                        "username": self.username.value,
                        "email": self.email.value,
                        "password": self.password.value,
                    },
                )
                result = await self.platform.register(ctx)
                if not result.success:
                    await interaction.followup.send(result.message)
                    return

                credentials = {
                    "url": self.url,
                    "username": self.username.value,
                    "password": self.password.value,
                    "email": self.email.value,
                    "_message": (
                        f"CTFd platform: {self.url}\n"
                        "```yaml\n"
                        f"Username: {self.username.value}\n"
                        f"Password: {self.password.value}\n"
                        "```"
                    ),
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
        await interaction.followup.send(
            result.message or "✅ Registration successful.", ephemeral=True
        )
