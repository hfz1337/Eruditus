"""Error message constants."""


class ErrorMessages:
    """Standard error messages used throughout the bot."""

    # Context errors
    NOT_IN_CTF_CHANNEL = "Run this command from within a CTF channel."
    NOT_IN_CHALLENGE_THREAD = "Run this command from within a challenge thread."

    # CTF errors
    CTF_NOT_FOUND = "No such CTF."
    CTF_ALREADY_EXISTS = "A CTF with this name already exists."
    CTF_ARCHIVED = "This CTF is archived."

    # Challenge errors
    CHALLENGE_NOT_FOUND = "No such challenge."
    CHALLENGE_ALREADY_EXISTS = "This challenge already exists."
    CHALLENGE_ALREADY_SOLVED = "This challenge was already solved."

    # Platform errors
    PLATFORM_NOT_SUPPORTED = "Platform not supported or invalid URL."
    NO_CREDENTIALS = "No credentials set for this CTF."

    # Permission errors
    ROLE_DELETED = "CTF role was deleted by an admin, aborting."
