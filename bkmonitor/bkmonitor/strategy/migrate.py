# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import typing

from django.apps.registry import Apps

from bkmonitor.utils.common_utils import chunks

ActionConfigInfo = typing.Dict[str, typing.Any]


def get_action_configs_generator(action_config_model, config_ids: typing.Set[int]):
    print(f"[to_be_updated_configs] total -> {len(config_ids)}")
    # 使用生成器分批查询，避免单次全量拉取导致 OOM
    for chunk_config_ids in chunks(list(config_ids), 500):
        action_configs: typing.List[ActionConfigInfo] = action_config_model.objects.filter(
            id__in=chunk_config_ids
        ).values("id", "execute_config")
        yield list(action_configs)


def fetch_action_configs(
    apps: Apps, strategy_ids: typing.Optional[typing.Set[int]] = None
) -> typing.Generator[typing.List[ActionConfigInfo], None, None]:

    action_config_model = apps.get_model("bkmonitor", "ActionConfig")
    relation_model = apps.get_model("bkmonitor", "StrategyActionConfigRelation")
    relations: typing.List[typing.Dict[str, int]] = relation_model.objects.values(
        "strategy_id", "config_id", "relate_type"
    )
    config_ids: typing.Set[int] = set()
    for relation in relations:
        if relation["relate_type"] == "NOTICE" and (strategy_ids is None or relation["strategy_id"] in strategy_ids):
            config_ids.add(relation["config_id"])

    yield from get_action_configs_generator(action_config_model, config_ids)


def fetch_action_configs_by_bizs(
    apps: Apps, bk_biz_ids: typing.List[str]
) -> typing.Generator[typing.List[ActionConfigInfo], None, None]:
    strategy_model = apps.get_model("bkmonitor", "StrategyModel")
    action_config_model = apps.get_model("bkmonitor", "ActionConfig")
    relation_model = apps.get_model("bkmonitor", "StrategyActionConfigRelation")

    strategy_ids: typing.Set[int] = set(
        strategy_model.objects.filter(bk_biz_id__in=bk_biz_ids).values_list("id", flat=True)
    )

    # 查询 ID 过多 SQL 性能退化，此时直接转为全部拉取 + 内存计算
    if len(strategy_ids) > 500:
        yield from fetch_action_configs(apps, strategy_ids)
    else:
        config_ids: typing.Set[int] = set(
            relation_model.objects.filter(strategy_id__in=strategy_ids, relate_type="NOTICE").values_list(
                "config_id", flat=True
            )
        )
        yield from get_action_configs_generator(action_config_model, config_ids)


def update_notice_template(apps: Apps, old: str, new: str, bk_biz_ids: typing.Optional[typing.List[str]] = None):

    if bk_biz_ids is None:
        action_configs_generator: typing.Generator[typing.List[ActionConfigInfo], None, None] = fetch_action_configs(
            apps
        )
    else:
        action_configs_generator: typing.Generator[
            typing.List[ActionConfigInfo], None, None
        ] = fetch_action_configs_by_bizs(apps, bk_biz_ids)

    count: int = 0
    strategy_model = apps.get_model("bkmonitor", "StrategyModel")
    action_config_model = apps.get_model("bkmonitor", "ActionConfig")
    relation_model = apps.get_model("bkmonitor", "StrategyActionConfigRelation")
    for index, action_configs in enumerate(action_configs_generator):
        is_change: bool = False
        to_be_updated_configs: typing.List[typing.Any] = []
        for action_config in action_configs:
            try:
                for template in action_config["execute_config"]["template_detail"]["template"]:
                    if (
                        template["message_tmpl"].strip() == old.strip()
                        or template["message_tmpl"].strip() == old.strip()
                    ):
                        template["message_tmpl"] = new
                        is_change = True
            except Exception:
                is_change = False

            if is_change:
                to_be_updated_configs.append(
                    action_config_model(
                        pk=action_config["id"], execute_config=action_config["execute_config"], hash="", snippet=""
                    )
                )

        count += len(to_be_updated_configs)
        action_config_model.objects.bulk_update(to_be_updated_configs, fields=["execute_config", "hash", "snippet"])

        # 找到关联的 strategy_ids，清理 hash & snippet
        # Q：为什么要清理 hash & snippet
        # A：hash & snippet 为 asCode 模块维护的配置唯一标识和片段，用于导入时校验配置是否相同，此处已做配置修改，需要进行重置
        strategy_ids: typing.List[int] = list(
            relation_model.objects.filter(
                config_id__in=[to_be_updated_config.pk for to_be_updated_config in to_be_updated_configs],
                relate_type="NOTICE",
            ).values_list("strategy_id", flat=True)
        )
        strategy_model.objects.filter(id__in=strategy_ids).update(hash="", snippet="")

        print(f"[to_be_updated_configs] idx -> {index}, update count -> {len(to_be_updated_configs)}")

    print(f"[to_be_updated_configs] finished: count -> {count}")

    return count
