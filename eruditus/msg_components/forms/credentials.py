from urllib.parse import parse_qs, urlparse

import discord

from config import CTF_COLLECTION, DBNAME, MONGO

# @todo: @es3n1n: Ideally we should generate a modal form by supplying the args that we
#  need w/o hard-coding them


class CTFdCredentialsForm(discord.ui.Modal, title="Add CTFd credentials"):
    username = discord.ui.TextInput(
        label="Username",
        style=discord.TextStyle.short,
        placeholder="Enter your username...",
        required=True,
        max_length=128,
    )
    password = discord.ui.TextInput(
        label="Password",
        style=discord.TextStyle.short,
        placeholder="Enter your password...",
        required=True,
        max_length=128,
    )

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    async def on_submit(self, interaction: discord.Interaction) -> None:
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctf["credentials"]["url"] = self.url
        ctf["credentials"]["username"] = self.username.value
        ctf["credentials"]["password"] = self.password.value

        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]},
            {"$set": {"credentials": ctf["credentials"]}},
        )

        creds_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
        )
        message = (
            f"CTFd platform: {self.url}\n"
            "```yaml\n"
            f"Username: {self.username.value}\n"
            f"Password: {self.password.value}\n"
            "```"
        )

        await creds_channel.purge()
        await creds_channel.send(message, suppress_embeds=True)
        await interaction.response.send_message("✅ Credentials added.", ephemeral=True)


class RCTFCredentialsForm(discord.ui.Modal, title="Add rCTF invite link"):
    invite = discord.ui.TextInput(
        label="Invite link",
        style=discord.TextStyle.short,
        placeholder="https://rctf.example.com/login?token=<token>",
        required=True,
        max_length=1024,
    )

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    async def on_submit(self, interaction: discord.Interaction) -> None:
        parsed_url = urlparse(self.invite.value)
        params = parse_qs(parsed_url.query)
        if not (team_token := params.get("token")):
            await interaction.response.send_message(
                "Token was not found in the URL, please submit a valid invite link.",
                ephemeral=True,
            )
            return
        team_token = team_token[0]

        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctf["credentials"]["url"] = self.url
        ctf["credentials"]["invite"] = self.invite.value
        ctf["credentials"]["teamToken"] = team_token

        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]},
            {"$set": {"credentials": ctf["credentials"]}},
        )

        creds_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
        )
        message = f"rCTF invite link: {self.invite.value}"

        await creds_channel.purge()
        await creds_channel.send(message, suppress_embeds=True)
        await interaction.response.send_message("✅ Credentials added.", ephemeral=True)


class DefaultCredentialsForm(discord.ui.Modal, title="Add CTF credentials"):
    username = discord.ui.TextInput(
        label="Username (if any)",
        style=discord.TextStyle.short,
        placeholder="Username...",
        required=False,
        max_length=128,
    )
    password = discord.ui.TextInput(
        label="Password (if any)",
        style=discord.TextStyle.short,
        placeholder="Password...",
        required=False,
        max_length=128,
    )

    invite = discord.ui.TextInput(
        label="Invite link (if any)",
        style=discord.TextStyle.short,
        placeholder="Invite url...",
        required=False,
        max_length=1024,
    )

    token = discord.ui.TextInput(
        label="Token (if any)",
        style=discord.TextStyle.short,
        placeholder="Token...",
        required=False,
        max_length=128,
    )

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    async def on_submit(self, interaction: discord.Interaction) -> None:
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctf["credentials"]["url"] = self.url
        ctf["credentials"]["username"] = self.username.value
        ctf["credentials"]["password"] = self.password.value
        ctf["credentials"]["invite"] = self.invite.value
        ctf["credentials"]["teamToken"] = self.token.value

        MONGO[DBNAME][CTF_COLLECTION].update_one(
            {"_id": ctf["_id"]},
            {"$set": {"credentials": ctf["credentials"]}},
        )

        creds_channel = discord.utils.get(
            interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
        )
        # fmt: off
        message = (
            f"CTF platfrom: {self.url}\n"
            f"Invite link: {self.invite.value}\n" if self.invite else ""
            "```yaml\n"
            f"Username: {self.username.value}\n" if self.username else ""
            f"Password: {self.password.value}\n" if self.password else ""
            f"Token: {self.token.value}\n" if self.token else ""
            "```"
        )
        # fmt: on

        await creds_channel.purge()
        await creds_channel.send(message, suppress_embeds=True)
        await interaction.response.send_message("✅ Credentials added.", ephemeral=True)
