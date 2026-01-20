"""Discord slash commands for Eruditus."""

from commands.bookmark import Bookmark
from commands.cipher import Cipher
from commands.ctf import CTF
from commands.ctftime import CTFTime
from commands.encoding import Encoding
from commands.help import Help
from commands.intro import Intro
from commands.report import Report
from commands.request import Request
from commands.revshell import Revshell
from commands.search import Search
from commands.syscalls import Syscalls
from commands.takenote import TakeNote

__all__ = [
    "Bookmark",
    "Cipher",
    "CTF",
    "CTFTime",
    "Encoding",
    "Help",
    "Intro",
    "Report",
    "Request",
    "Revshell",
    "Search",
    "Syscalls",
    "TakeNote",
]
