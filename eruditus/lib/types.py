from enum import Enum


class CPUArchitecture(Enum):
    x86 = 1
    x64 = 2
    arm = 3
    armthumb = 4


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
