"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from typing import Any
from collections.abc import Iterable

from rest_framework import serializers

from apm_web.models import StrategyTemplate
from bkmonitor.utils.common_utils import count_md5

from .query_template import QueryTemplateWrapperFactory

from core.drf_resource import resource
from bkmonitor.models import UserGroup

from constants.query_template import GLOBAL_BIZ_ID


def format2strategy_template_detail(
    strategy_template_obj: StrategyTemplate, serializer: type[serializers.Serializer]
) -> dict[str, Any]:
    """生成策略模板详情数据"""
    strategy_template_data: dict[str, Any] = serializer(strategy_template_obj).data
    query_template_data: dict[str, Any] = strategy_template_data["query_template"]
    qtw = QueryTemplateWrapperFactory.get_wrapper(
        query_template_data.get("bk_biz_id", GLOBAL_BIZ_ID), query_template_data.get("name", "")
    )
    if qtw is not None:
        query_template_data.update(qtw.to_dict())
    return strategy_template_data


def get_user_groups(user_group_ids: Iterable[int]) -> dict[int, dict[str, int | str]]:
    """获取用户组 ID 到 用户组简要信息的映射关系"""
    return {
        user_group["id"]: user_group
        for user_group in UserGroup.objects.filter(id__in=user_group_ids).values("id", "name")
    }


def get_id_strategy_map(bk_biz_id: int, ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """获取策略 ID 到 策略简要信息的映射关系"""
    if not ids:
        return {}

    strategies: list[dict[str, Any]] = resource.strategies.plain_strategy_list(
        {"bk_biz_id": bk_biz_id, "ids": list(ids)}
    )
    return {
        strategy_dict["id"]: {"id": strategy_dict["id"], "name": strategy_dict["name"]} for strategy_dict in strategies
    }


def simplify_conditions(conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    简化过滤条件，去除重复条件。
    - A A B C or D D -> A B C or D
    - A or B or A -> A or B
    :param conditions: 过滤条件列表。
    :return:
    """
    start: int = 0
    seen_conditions_md5: set[str] = set()
    simplified_conditions: list[dict[str, Any]] = []
    for idx, condition in enumerate(conditions):
        is_end: bool = idx == len(conditions) - 1
        is_need_truncate: bool = condition.get("condition") == "or" or is_end
        if not is_need_truncate:
            continue

        end: int = idx + 1 if is_end else idx
        if start >= end:
            continue

        seen: set[str] = set()
        simplified_partial_conditions: list[dict[str, Any]] = []
        for cond in conditions[start:end]:
            copy_cond: dict[str, Any] = copy.deepcopy(cond)
            copy_cond.pop("condition", None)
            cond_md5: str = count_md5(copy_cond)
            if cond_md5 in seen:
                continue

            seen.add(cond_md5)
            simplified_partial_conditions.append(cond)

        start = idx

        copy_partial_conditions: list[dict[str, Any]] = copy.deepcopy(simplified_partial_conditions)
        for cond in copy_partial_conditions:
            cond.pop("condition", None)

        conditions_md5: str = count_md5(copy_partial_conditions)
        if conditions_md5 in seen_conditions_md5:
            continue

        # 如果 OR 的两段条件相同，只保留一段。
        seen_conditions_md5.add(conditions_md5)
        simplified_conditions.extend(simplified_partial_conditions)

    return simplified_conditions
