from typing import Awaitable, Callable, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import discord

from config import CTF_COLLECTION, DBNAME, MONGO
from lib.platforms import Platform, PlatformCTX


class CredentialsForm(discord.ui.Modal, title="Add CTF credentials"):
    def __init__(
        self,
        url: str,
        platform: Optional[Platform],
        callback: Callable[..., Awaitable[None]],
        **kwargs,
    ) -> None:
        super().__init__()

        self.url = url
        self.platform = platform
        self.callback = callback

        for key in kwargs:
            setattr(self, key, discord.ui.TextInput(**kwargs[key]))
            self.add_item(getattr(self, key))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        await self.callback(self, interaction)


async def add_credentials_callback(
    self: CredentialsForm, interaction: discord.Interaction
) -> None:
    def extract_team_token() -> str:
        parsed_url = urlparse(self.invite.value)
        params = parse_qs(parsed_url.query)
        if not (team_token := params.get("token")):
            return self.invite.value

        return team_token[0]

    match Platform(self.platform):
        case Platform.RCTF:
            team_token = extract_team_token()

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


async def register_account_callback(
    self: CredentialsForm, interaction: discord.Interaction
) -> None:
    match Platform(self.platform):
        case Platform.RCTF:
            ctx: PlatformCTX = PlatformCTX(
                base_url=self.url,
                args={"team": self.username.value, "email": self.email.value},
            )
            result = await self.platform.value.register(ctx)
            if not result.success:
                await interaction.followup.send(result.message)
                return

            invite_url = f"{ctx.url_stripped}/login?" + urlencode(
                {"token": result.invite}
            )
            credentials = {
                "url": self.url,
                "team": self.username.value,
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
            result = await self.platform.value.register(ctx)
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


def create_credentials_modal_for_platform(
    url: str, platform: Optional[Platform], is_registration: bool = False
) -> Optional[CredentialsForm]:
    def make_fields(*args: str, **kwargs: dict) -> dict:
        """A util that is used for creation of the modal fields."""
        result = dict()

        def proceed(name: str, config: Optional[dict] = None) -> None:
            if config is None:
                config = dict()

            def forward(**kw: str | bool | int | discord.TextStyle) -> dict[str, str]:
                forwarded: dict[str, str] = dict()

                for kw_k, kw_v in kw.items():
                    forwarded[kw_k] = config.get(kw_k, kw_v)

                return forwarded

            def make_text_input(
                label: str,
                placeholder: str,
                required: bool = True,
                max_length: int = 128,
                style: discord.TextStyle = discord.TextStyle.short,
            ) -> dict:
                """A util that is used to simplify the text inputs creation."""
                return forward(
                    label=label,
                    placeholder=placeholder,
                    required=required,
                    max_length=max_length,
                    style=style,
                )

            match name:
                case "email":
                    result[name] = make_text_input("Email", "Enter your email...")
                case "username":
                    result[name] = make_text_input("Username", "Enter your username...")
                case "password":
                    result[name] = make_text_input("Password", "Enter your password...")
                case "invite":
                    result[name] = make_text_input(
                        "Invite link", "Enter your team invite URL...", max_length=512
                    )
                case "token":
                    result[name] = make_text_input(
                        "Token", "Enter your team token...", max_length=256
                    )

        for field_name in args:
            proceed(field_name)

        for k, v in kwargs.items():
            proceed(k, v)

        return result

    callback = (
        register_account_callback if is_registration else add_credentials_callback
    )

    match Platform(platform):
        # CTFd platform
        case Platform.CTFd:
            return CredentialsForm(
                url=url,
                platform=Platform.CTFd,
                callback=callback,
                **make_fields(
                    "username", "password", *(["email"] if is_registration else [])
                ),
            )

        # rCTF platform
        case Platform.RCTF:
            return CredentialsForm(
                url=url,
                platform=Platform.RCTF,
                callback=callback,
                **(
                    make_fields(
                        invite=dict(
                            label="rCTF invite link",
                            placeholder="https://rctf.example.com/login?token=<token>",
                        )
                    )
                    if not is_registration
                    else make_fields("username", "email")
                ),
            )

    # No default form for registration command
    if is_registration:
        return None

    # Unknown platform
    return CredentialsForm(
        url=url,
        platform=None,
        callback=callback,
        **make_fields(
            "username",
            password=dict(required=False),
            invite=dict(required=False),
            token=dict(required=False),
        ),
    )
