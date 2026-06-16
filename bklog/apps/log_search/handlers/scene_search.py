"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""


class AllConditionsBuilder:
    """
    Validate and pass through table_id_conditions in the AllConditions format
    ([][]ConditionField) for unify-query scene-based routing.

    - Inner list: AND group (all conditions must match)
    - Outer list: OR  groups (any group match is sufficient)

    Frontend is responsible for building the conditions structure;
    this class only validates the raw input.
    """

    VALID_OPS = {"eq", "ne", "req", "nreq"}

    @classmethod
    def from_raw(cls, conditions: list[list[dict]]) -> list[list[dict]]:
        """Validate and pass through raw AllConditions provided by the caller."""
        for and_group in conditions:
            for cond in and_group:
                if cond.get("op", "eq") not in cls.VALID_OPS:
                    raise ValueError(f"Invalid op: {cond['op']}")
                if "field_name" not in cond or "value" not in cond:
                    raise ValueError(f"Missing field_name or value in condition: {cond}")
        return conditions
