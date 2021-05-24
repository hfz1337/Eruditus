#
# Eruditus - Syscalls cog
#
# ======================================================================================
# Shows information about a syscall from a specific CPU architecture.
# Credits: https://github.com/OpenToAllCTF/OTA-Challenge-Bot/tree/master/addons/syscalls
#
# The code for the SyscallTable class is mainly brought from the aforementioned
# repository, but I changed some parts of it to make it more suitable to my coding taste
# The syscalls tables under `tables` were integrated without any changes.
# ======================================================================================

from discord.ext.commands import Context, Bot
from collections import OrderedDict
from discord.ext import commands
from help import help_info
import discord
import os


class SyscallTable:
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
    def __init__(self, bot: Bot, basedir: str) -> None:
        self.bot = bot
        self.tables = {}

        for table in os.listdir(basedir):
            self.tables[table] = SyscallTable(os.path.join(basedir, table))

    @commands.group()
    async def syscalls(self, ctx: Context) -> None:
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"Commands group for {self.bot.command_prefix}{ctx.invoked_with}",
                colour=discord.Colour.blue(),
            ).set_thumbnail(url=f"{self.bot.user.avatar_url}")

            for command in help_info[ctx.invoked_with]:
                embed.add_field(
                    name=help_info[ctx.invoked_with][command]["usage"].format(
                        self.bot.command_prefix
                    ),
                    value=help_info[ctx.invoked_with][command]["brief"],
                    inline=False,
                )

            await ctx.send(embed=embed)

    @syscalls.command()
    async def available(self, ctx: Context) -> None:
        await ctx.send(f"Supported architectures: {', '.join(self.tables.keys())}")

    @syscalls.command()
    async def show(self, ctx: Context, arch: str, syscall: str) -> None:
        # make sure the arch exists
        if arch not in self.tables.keys():
            await ctx.send(f"No such architecture: {arch}")

        table = self.tables.get(arch)

        if syscall.startswith("0x"):
            entry = table.get_entry_by_id(int(syscall, 16))
        elif syscall.isdigit():
            entry = table.get_entry_by_id(int(syscall))
        else:
            entry = table.get_entry_by_name(syscall)

        if entry is None:
            await ctx.send(
                f"No such syscall{' id' if syscall.isdigit() else ''}: {syscall}"
            )

        info = "\n".join(f"{key + ':':15} {entry[key]}" for key in entry)

        await ctx.send(f"```yaml\n{info}\n```")


def setup(bot: Bot) -> None:
    bot.add_cog(Syscalls(bot, "tables"))
