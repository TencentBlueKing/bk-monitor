from constants.issue import IssueStatus, IssuePriority, ImpactScopeDimension
from fta_web.alert.handlers.translator import AbstractTranslator


class StatusTranslator(AbstractTranslator):
    """Issue 状态翻译"""

    def translate(self, values: list) -> dict:
        status_map = dict(IssueStatus.CHOICES)
        return {v: str(status_map.get(v, v)) for v in values}


class PriorityTranslator(AbstractTranslator):
    """Issue 优先级翻译"""

    def translate(self, values: list) -> dict:
        priority_map = dict(IssuePriority.CHOICES)
        return {v: str(priority_map.get(v, v)) for v in values}


class ImpactDimensionsTranslator(AbstractTranslator):
    """影响范围维度翻译"""

    def translate(self, values: list) -> dict:
        return {v: str(ImpactScopeDimension.get_display_name(v)) for v in values}
