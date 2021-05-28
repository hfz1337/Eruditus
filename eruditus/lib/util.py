from string import ascii_lowercase, digits
from hashlib import md5


def sanitize_channel_name(name: str) -> str:
    """Filters out characters that aren't allowed by Discord for guild channels.

    Args:
        name: Channel name.

    Returns:
        Sanitized channel name.

    """
    whitelist = ascii_lowercase + digits + "-_"
    name = name.lower().replace(" ", "-")

    for char in name:
        if char not in whitelist:
            name = name.replace(char, "")

    while "--" in name:
        name = name.replace("--", "-")

    return name


def derive_colour(role_name: str) -> int:
    """Derives a colour for the CTF role by taking its MD5 hash and using the first 3
    bytes as the colour.

    Args:
        role_name: Name of the role we wish to set a colour for.

    Returns:
        An integer representing an RGB colour.

    """
    return int(md5(role_name.encode()).hexdigest()[:6], 16)
