"""组合策略。当前迁移期只用 Union（任一 ALLOW 即过），没有 AllOf / Primary。"""

from apps.iam.iam_engine.provider.composition.union import UnionDecisionPolicy, UnionScopePolicy

__all__ = ["UnionDecisionPolicy", "UnionScopePolicy"]
