from enum import Enum


class DeviceType(Enum):
    PC = 'PC'
    MOBILE = 'MOBILE'
    UNKNOWN = 'UNKNOWN'


class TokenType(Enum):
    ACCESS_TOKEN = 'ACCESS_TOKEN'
    REFRESH_TOKEN = 'REFRESH_TOKEN'
