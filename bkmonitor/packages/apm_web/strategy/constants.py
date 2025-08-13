import enum


class QueryTemplateVariableType(enum.Enum):
    GROUP_BY = "GROUP_BY"
    AGG = "AGG"
    DIMENSION_VALUE = "DIMENSION_VALUE"
    CONDITIONS = "CONDITIONS"
    FUNCTIONS = "FUNCTIONS"
    CONSTANTS = "CONSTANTS"

    @classmethod
    def choices(cls):
        return [(item.name, item.value) for item in cls]


class QueryTemplateRelationType(enum.Enum):
    ALERT_POLICY = "ALERT_POLICY"
    DASHBOARD = "DASHBOARD"
