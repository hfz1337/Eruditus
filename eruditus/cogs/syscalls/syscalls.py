from collections import OrderedDict
import os

from discord.ext.commands import Bot
from discord.ext import commands

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from cogs.syscalls.help import cog_help


class SyscallTable:
    """Represents an architecture's syscall table."""

    def __init__(self, filename: str) -> None:
        self.entries = OrderedDict()

        # this is used in order to retrieve a syscall by id without
        # looping through the entries everytime we need to look it up
        self.lookup = {}

        self.parse_table(filename)

    def parse_table(self, filename: str) -> None:
        lines = [line.split("\t") for line in open(filename).readlines()]

        for line in lines[1:]:
            entry = OrderedDict()

            for idx, identifier in enumerate(lines[0]):
                identifier = identifier.strip()
                if identifier == "Definition":
                    entry[identifier] = line[idx].split(":")[0]
                    continue

                entry[identifier] = line[idx]

            self.entries[line[1]] = entry
            self.lookup[int(entry["id"])] = entry["Name"]

    def get_entry_by_id(self, idx: int) -> OrderedDict:
        if idx in self.lookup:
            return self.entries.get(self.lookup[idx])

        return None

    def get_entry_by_name(self, name: str) -> OrderedDict:
        return self.entries.get(name)

    def get_field_by_id(self, idx: int, field: str):
        entry = self.get_entry_by_id(idx)

        if entry is None or field not in entry:
            return None

        return entry[field]

    def get_field_by_name(self, name: str, field: str) -> str:
        entry = self.get_entry_by_name(name)

        if entry is None or field not in entry:
            return None

        return entry[field]


class Syscalls(commands.Cog):
    """This cog provides information for a syscall from a specific architecture."""

    def __init__(self, bot: Bot, basedir: str) -> None:
        self.bot = bot
        self.tables = {}

        for table in os.listdir(basedir):
            self.tables[table] = SyscallTable(os.path.join(basedir, table))

    @cog_ext.cog_slash(
        name=cog_help["name"],
        description=cog_help["description"],
        options=[create_option(**option) for option in cog_help["options"]],
    )
    async def _syscalls(self, ctx: SlashContext, arch: str, syscall: str) -> None:
        """Show information for a syscall from a specific architecture.

        Args:
            ctx: The context in which the command is being invoked under.
            arch: The architecture.
            syscall: The syscall name or ID (in hex or decimal).
        """
        table = self.tables.get(arch)

        if syscall.startswith("0x"):
            try:
                syscall_decimal = int(syscall, 16)
                entry = table.get_entry_by_id(syscall_decimal)
            except ValueError:
                entry = None
        elif syscall.isdigit():
            entry = table.get_entry_by_id(int(syscall))
        else:
            entry = table.get_entry_by_name(syscall)

        if entry is None:
            await ctx.send(
                f"No such syscall{' id' if syscall.isdigit() else ''}: {syscall}"
            )
        else:
            info = "\n".join(f"{key + ':':15} {entry[key]}" for key in entry)
            await ctx.send(f"```yaml\n{info}\n```")


def setup(bot: Bot) -> None:
    """Add the extension to the bot."""
    cog_dir = os.path.dirname(os.path.abspath(__file__))
    bot.add_cog(Syscalls(bot, f"{cog_dir}/tables"))
