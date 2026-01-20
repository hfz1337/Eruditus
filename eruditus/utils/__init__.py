"""Utility modules for Eruditus."""

from utils.countries import country_name
from utils.crypto import derive_colour
from utils.discord import make_form_field_config
from utils.formatting import (
    extract_filename_from_url,
    html_to_markdown,
    sanitize_channel_name,
    truncate,
)
from utils.html import (
    convert_attachment_url,
    extract_images_from_html,
    parse_attachment,
)
from utils.http import (
    deserialize_response,
    extract_rctf_team_token,
    strip_url_components,
)
from utils.responses import (
    CTFContextMixin,
    require_challenge_thread,
    require_ctf_context,
    send_error,
    send_info,
    send_response,
    send_success,
    send_warning,
)
from utils.time import get_local_time
from utils.validation import in_range, is_empty_string
from utils.visualization import plot_scoreboard

__all__ = [
    "truncate",
    "sanitize_channel_name",
    "html_to_markdown",
    "extract_filename_from_url",
    "get_local_time",
    "derive_colour",
    "in_range",
    "is_empty_string",
    "strip_url_components",
    "extract_rctf_team_token",
    "deserialize_response",
    "convert_attachment_url",
    "parse_attachment",
    "extract_images_from_html",
    "make_form_field_config",
    "country_name",
    "plot_scoreboard",
    "send_response",
    "send_error",
    "send_success",
    "send_warning",
    "send_info",
    "require_ctf_context",
    "require_challenge_thread",
    "CTFContextMixin",
]
