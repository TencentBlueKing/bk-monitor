"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import typing

from django.apps.registry import Apps

from bkmonitor.utils.common_utils import chunks

ActionConfigInfo = dict[str, typing.Any]


def get_action_configs_generator(action_config_model, config_ids: set[int]):
    print(f"[to_be_updated_configs] total -> {len(config_ids)}")
    # 使用生成器分批查询，避免单次全量拉取导致 OOM
    for chunk_config_ids in chunks(list(config_ids), 500):
        action_configs: list[ActionConfigInfo] = action_config_model.objects.filter(id__in=chunk_config_ids).values(
            "id", "execute_config"
        )
        yield list(action_configs)


def fetch_action_configs(
    apps: Apps, strategy_ids: set[int] | None = None
) -> typing.Generator[list[ActionConfigInfo], None, None]:
    action_config_model = apps.get_model("bkmonitor", "ActionConfig")
    relation_model = apps.get_model("bkmonitor", "StrategyActionConfigRelation")
    relations: list[dict[str, int]] = relation_model.objects.values("strategy_id", "config_id", "relate_type")
    config_ids: set[int] = set()
    for relation in relations:
        if relation["relate_type"] == "NOTICE" and (strategy_ids is None or relation["strategy_id"] in strategy_ids):
            config_ids.add(relation["config_id"])

    yield from get_action_configs_generator(action_config_model, config_ids)


def fetch_action_configs_by_bizs(
    apps: Apps, bk_biz_ids: list[str]
) -> typing.Generator[list[ActionConfigInfo], None, None]:
    strategy_model = apps.get_model("bkmonitor", "StrategyModel")
    action_config_model = apps.get_model("bkmonitor", "ActionConfig")
    relation_model = apps.get_model("bkmonitor", "StrategyActionConfigRelation")

    strategy_ids: set[int] = set(strategy_model.objects.filter(bk_biz_id__in=bk_biz_ids).values_list("id", flat=True))

    # 查询 ID 过多 SQL 性能退化，此时直接转为全部拉取 + 内存计算
    if len(strategy_ids) > 500:
        yield from fetch_action_configs(apps, strategy_ids)
    else:
        config_ids: set[int] = set(
            relation_model.objects.filter(strategy_id__in=strategy_ids, relate_type="NOTICE").values_list(
                "config_id", flat=True
            )
        )
        yield from get_action_configs_generator(action_config_model, config_ids)
