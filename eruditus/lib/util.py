from string import ascii_lowercase, digits
from hashlib import md5


def sanitize_channel_name(name: str) -> str:
    whitelist = ascii_lowercase + digits + "-_"
    name = name.lower().replace(" ", "-")

    for char in name:
        if char not in whitelist:
            name = name.replace(char, "")

    while "--" in name:
        name = name.replace("--", "-")

    return name


def derive_colour(string: str) -> int:
    return int(md5(string.encode()).hexdigest()[:6], 16)
