"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils import timezone
from . import rpc, metric

from apm_web.models.strategy import StrategyTemplate

BUILTIN_STRATEGY_TEMPLATES = [rpc.RPCStrategyTemplateSet, metric.MetricStrategyTemplateSet]


def register_builtin_template(bk_biz_id: int, app_name: int) -> None:
    # TODO 识别应用的框架、语言，再决定注册哪些内置模板。
    systems: list[str] = [builtin.SYSTEM.value for builtin in BUILTIN_STRATEGY_TEMPLATES]
    tmpl_code__id_map: dict[str, int] = {
        tmpl["code"]: tmpl["id"]
        for tmpl in StrategyTemplate.origin_objects.filter(bk_biz_id=bk_biz_id, system__in=systems).values("code", "id")
    }

    to_be_created: list[StrategyTemplate] = []
    to_be_updated: list[StrategyTemplate] = []
    local_tmpl_codes: set[str] = set()
    remote_tmpl_codes: set[str] = set(tmpl_code__id_map.keys())
    for builtin in BUILTIN_STRATEGY_TEMPLATES:
        for template in builtin.QUERY_TEMPLATES:
            # TODO 开放配置项，允许根据应用场景，内置更多模板。
            if template["code"] not in builtin.ENABLED_CODES:
                continue

            obj: StrategyTemplate = StrategyTemplate(**template)
            obj.bk_biz_id, obj.app_name, obj.system = bk_biz_id, app_name, builtin.SYSTEM.value
            if obj.code in tmpl_code__id_map:
                # TODO 被用户更新过的，不再进行更新
                obj.update_user = "system"
                obj.update_time = timezone.now()
                obj.pk = tmpl_code__id_map[obj.code]
                to_be_updated.append(obj)
            else:
                obj.create_user = obj.update_user = "system"
                to_be_created.append(obj)

            local_tmpl_codes.add(obj.code)

    StrategyTemplate.objects.bulk_create(to_be_created)
    StrategyTemplate.objects.bulk_update(
        to_be_updated,
        fields=[
            "name",
            "root_id",
            "parent_id",
            "category",
            "monitor_type",
            "detect",
            "algorithms",
            "user_group_ids",
            "query_template",
            "context",
            "update_user",
            "update_time",
        ],
    )

    to_be_deleted: list[str] = list(remote_tmpl_codes - local_tmpl_codes)
    if to_be_deleted:
        StrategyTemplate.origin_objects.filter(bk_biz_id=bk_biz_id, code__in=to_be_deleted).update(is_deleted=True)
