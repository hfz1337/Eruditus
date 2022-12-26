from enum import Enum


class CPUArchitecture(Enum):
    x86 = 1
    x64 = 2
    arm = 3
    armthumb = 4


class EncodingOperationMode(Enum):
    encode = 1
    decode = 2


class ArchiveMode(Enum):
    minimal = 1
    all = 2


class CTFStatusMode(Enum):
    active = 1
    all = 2


class NoteType(Enum):
    progress = 1
    note = 2


class NoteFormat(Enum):
    embed = 1
    raw = 2


class PromptPrivacy(Enum):
    private = 1
    public = 0
