from typing import Awaitable, Callable, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import discord

from lib.discord_util import update_credentials
from lib.platforms import Platform, PlatformABC, PlatformCTX
from lib.util import (
    extract_rctf_team_token,
    make_form_field_config,
    strip_url_components,
)


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

        for key, value in kwargs.items():
            setattr(self, key, discord.ui.TextInput(**value))
            self.add_item(getattr(self, key))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.callback(self, interaction)


async def add_credentials_callback(
    self: CredentialsForm, interaction: discord.Interaction
) -> None:
    await interaction.response.defer()
    match Platform(self.platform):
        case Platform.RCTF:
            invite = self.invite.value or self.url
            self.url = strip_url_components(self.url)
            team_token = extract_rctf_team_token(invite)
            if team_token is None:
                await interaction.followup.send(
                    (
                        "Token was not found in the URL, please submit a valid "
                        "invite link."
                    ),
                    ephemeral=True,
                )
                return

            credentials = {
                "url": self.url,
                "teamToken": team_token,
                "invite": invite,
                "_message": (
                    f"rCTF platform: {self.url}\n"
                    f"Invite link: {invite}\n"
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

    msg = "✅ Credentials added."

    # Try to authorize.
    if self.platform is not None and self.platform.value is not None:
        ctx = PlatformCTX.from_credentials(credentials)
        session = await self.platform.value.login(ctx)

        if not session or not session.validate():
            await interaction.followup.send(
                "❌ Unable to authorize on the platform.", ephemeral=True
            )
            return

        me = await self.platform.value.get_me(ctx)
        if me:
            msg += f" Authorized as `{me.name}`"

    # Add credentials.
    await update_credentials(interaction, credentials)
    await interaction.followup.send(msg, ephemeral=True)


async def register_account_callback(
    self: CredentialsForm, interaction: discord.Interaction
) -> None:
    await interaction.response.defer()
    match Platform(self.platform):
        case Platform.RCTF:
            ctx: PlatformCTX = PlatformCTX(
                base_url=self.url,
                args={"team": self.username.value, "email": self.email.value},
            )
            result = await self.platform.value.register(ctx)
            if not result.success:
                await interaction.followup.send(result.message, ephemeral=True)
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
                await interaction.followup.send(result.message, ephemeral=True)
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

        case _:
            return

    # Add credentials.
    await update_credentials(interaction, credentials)
    await interaction.followup.send(
        result.message or "✅ Registration successful.", ephemeral=True
    )


async def create_credentials_modal_for_platform(
    url: str,
    platform: Optional[PlatformABC],
    interaction: discord.Interaction,
    is_registration: bool = False,
) -> Optional[CredentialsForm]:
    def make_fields(*args: str, **kwargs: dict) -> dict:
        """A util that is used for creation of the modal fields."""
        fields = {field_name: {} for field_name in args} | kwargs
        return {
            field_name: make_form_field_config(field_name, config)
            for field_name, config in fields.items()
        }

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
            form = CredentialsForm(
                url=url,
                platform=Platform.RCTF,
                callback=callback,
                **(
                    make_fields(
                        invite={
                            "label": "rCTF invite link",
                            "placeholder": (
                                "https://rctf.example.com/login?token=<token>"
                            ),
                        }
                    )
                    if not is_registration
                    else make_fields("username", "email")
                ),
            )

            # Don't send the form if the URL already contains the token and we're just
            # adding credentials, not doing registration.
            if not is_registration:
                parsed_url = urlparse(url)
                if parsed_url.path.endswith("/login") and "token" in parse_qs(
                    parsed_url.query
                ):
                    await add_credentials_callback(form, interaction)
                    return None

            return form

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
            password={"required": False},
            invite={"required": False},
            token={"required": False},
            email={"required": False},
        ),
    )
