import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Union

import discord
from discord.ext import tasks
from discord.utils import MISSING


class CPUArchitecture(Enum):
    x86 = 1
    x64 = 2
    arm = 3
    armthumb = 4
    riscv = 5


class EncodingOperationMode(Enum):
    encode = 1
    decode = 2


class CTFStatusMode(Enum):
    active = 1
    all = 2


class Permissions(Enum):
    RDONLY = 0
    RDWR = 2


class OSType(Enum):
    linux = 0
    windows = 1
    mac = 2


class Privacy(Enum):
    public = 0
    private = 1


@dataclass
class CronJob(ABC):
    client: Optional[discord.Client] = None
    seconds: float = MISSING
    minutes: float = MISSING
    hours: float = MISSING
    time: Union[datetime.time, Sequence[datetime.time]] = MISSING
    count: Optional[int] = None
    reconnect: bool = True

    @abstractmethod
    async def run(self):
        pass

    def bind_client(self, client: discord.Client):
        self.client = client

    def create_task(self):
        return tasks.loop(
            seconds=self.seconds,
            minutes=self.minutes,
            hours=self.hours,
            count=self.count,
            reconnect=self.reconnect,
        )(self.run)
