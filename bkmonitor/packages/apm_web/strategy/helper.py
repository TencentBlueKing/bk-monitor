"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from collections.abc import Iterable

from rest_framework import serializers

from apm_web.models import StrategyTemplate

from .query_template import QueryTemplateWrapperFactory

from bkmonitor.models import UserGroup

from constants.query_template import GLOBAL_BIZ_ID


def format2strategy_template_detail(
    strategy_template_obj: StrategyTemplate, serializer: type[serializers.Serializer]
) -> dict[str, Any]:
    strategy_template_data: dict[str, Any] = serializer(strategy_template_obj).data
    query_template_data: dict[str, Any] = strategy_template_data["query_template"]
    qtw = QueryTemplateWrapperFactory.get_wrapper(
        query_template_data.get("bk_biz_id", GLOBAL_BIZ_ID), query_template_data.get("name", "")
    )
    if qtw is not None:
        query_template_data.update(qtw.to_dict())
    return strategy_template_data


def get_user_groups(user_group_ids: Iterable[int]) -> dict[int, dict[str, int | str]]:
    return {
        user_group["id"]: user_group
        for user_group in UserGroup.objects.filter(id__in=user_group_ids).values("id", "name")
    }
