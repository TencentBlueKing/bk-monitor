from enum import Enum


class AuthMode(str, Enum):
    V3 = "v3"
    V4 = "v4"
    UNION = "union"
