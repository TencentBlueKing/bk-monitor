import enum


class QueryTemplateVariableType(enum.Enum):
    GROUP_BY = "GROUP_BY"
    METHOD = "METHOD"
    TAG_VALUES = "TAG_VALUES"
    CONDITIONS = "CONDITIONS"
    FUNCTIONS = "FUNCTIONS"
    CONSTANTS = "CONSTANTS"

    @classmethod
    def choices(cls):
        return [(item.name, item.value) for item in cls]


class QueryTemplateVariableDataType(enum.Enum):
    INTERGER = "INTERGER"
    STRING = "STRING"

    @classmethod
    def choices(cls):
        return [(item.name, item.value) for item in cls]


class QueryTemplateRelationType(enum.Enum):
    ALERT_POLICY = "ALERT_POLICY"
    DASHBOARD = "DASHBOARD"
