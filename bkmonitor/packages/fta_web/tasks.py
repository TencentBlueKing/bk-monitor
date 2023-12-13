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
import logging
import time

from celery.task import task
from django.conf import settings
from django.utils.translation import ugettext as _

from bkmonitor.models import ActionConfig, AlertAssignGroup, AlertAssignRule
from core.drf_resource import api, resource
from fta_web.constants import QuickSolutionsConfig
from monitor_web.strategies.built_in import run_build_in
from monitor_web.strategies.user_groups import create_default_notice_group

logger = logging.getLogger("celery")


@task(ignore_result=True)
def update_home_statistics():
    # 更新首页的统计数据
    for days in [1, 7, 15, 30]:
        start_time = time.time()
        resource.home.all_biz_statistics.request.refresh(days=days)
        end_time = time.time()
        logger.info("[update_home_statistics] refresh %s days data in %ss", days, end_time - start_time)


@task(ignore_result=True)
def run_init_builtin(bk_biz_id):
    if bk_biz_id and settings.ENVIRONMENT != "development":
        logger.info("[run_init_builtin] enter with bk_biz_id -> %s", bk_biz_id)
        # 创建默认内置策略
        run_build_in(int(bk_biz_id))

        # 创建k8s内置策略
        run_build_in(int(bk_biz_id), mode="k8s")

        if (
            settings.ENABLE_DEFAULT_STRATEGY
            and int(bk_biz_id) > 0
            and not ActionConfig.origin_objects.filter(bk_biz_id=bk_biz_id, is_builtin=True).exists()
        ):
            logger.warning("[run_init_builtin] home run_init_builtin_action_config: bk_biz_id -> %s", bk_biz_id)
            # 如果当前页面没有出现内置套餐，则会进行快捷套餐的初始化
            try:
                run_init_builtin_action_config.delay(bk_biz_id)
            except Exception as error:
                # 直接忽略
                logger.exception(
                    "[run_init_builtin] run_init_builtin_action_config failed: bk_biz_id -> %s, error -> %s",
                    bk_biz_id,
                    str(error),
                )
        # TODO 先关闭，后面稳定了直接打开
        # if not AlertAssignGroup.origin_objects.filter(bk_biz_id=cc_biz_id, is_builtin=True).exists():
        #     # 如果当前页面没有出现内置的规则组
        #     run_init_builtin_assign_group(cc_biz_id)
    else:
        logger.info("[run_init_builtin] skipped with bk_biz_id -> %s", bk_biz_id)


@task(ignore_result=True)
def run_init_builtin_action_config(bk_biz_id):
    # 为业务初始化快捷套餐
    # 在当前业务下注册对应的快捷内容
    if ActionConfig.origin_objects.filter(bk_biz_id=bk_biz_id, is_builtin=True).exists():
        logger.info("[init_builtin_action_config(%s)] builtin config is existed", bk_biz_id)
        return

    try:
        for template_data in [
            QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE,
            QuickSolutionsConfig.IDLE_TEMPLATE,
        ]:
            api.sops.import_project_template(project_id=bk_biz_id, template_data=template_data)
    except BaseException as error:
        logger.exception("[init_builtin_action_config(%s)] error: %s", bk_biz_id, str(error))
        return

    actions = []

    all_templates = api.sops.get_template_list(bk_biz_id=bk_biz_id)
    for template in all_templates:
        if template["name"] not in QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.values():
            continue
        for config_key, name in QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.items():
            solution_name = QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.get(config_key, {}).get("name")
            if not solution_name:
                continue
            if (
                name == template["name"]
                and not ActionConfig.objects.filter(name=solution_name, bk_biz_id=bk_biz_id).exists()
            ):
                # 当前模板没有创建快捷套餐，则创建
                action_config = {
                    "is_builtin": True,
                    "name": solution_name,
                    "plugin_id": 4,
                    "bk_biz_id": bk_biz_id,
                    "desc": _("系统内置快捷套餐"),
                    "execute_config": {
                        "template_detail": QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG[config_key]["template_detail"],
                        "template_id": template["id"],
                        "timeout": 600,
                    },
                }
                actions.append(ActionConfig.objects.create(**action_config).name)
                break
    logger.info("[init_builtin_action_config(%s)] finished, create configs %s", bk_biz_id, ",".join(actions))


def run_init_builtin_assign_group(bk_biz_id):
    # 初始化全局告警分派规则
    if AlertAssignGroup.origin_objects.filter(bk_biz_id=bk_biz_id, is_builtin=True).exists():
        # 曾经内置过被删除了，忽略
        return

    user_group_id = create_default_notice_group(bk_biz_id, group_name=_("运维"))
    public_rule_info = dict(
        user_groups=[user_group_id],
        actions=[
            {
                'is_enabled': True,
                'action_type': 'notice',
                'upgrade_config': {'is_enabled': False, 'user_groups': [], 'upgrade_interval': 0},
            }
        ],
        bk_biz_id=bk_biz_id,
        is_enabled=True,
        alert_severity=0,
        additional_tags=[],
    )

    assign_group = AlertAssignGroup.objects.create(
        priority=1, is_builtin=True, name="[内置]第三方告警默认规则组", bk_biz_id=bk_biz_id
    )

    third_alert_rule = {
        "assign_group_id": assign_group.id,
        "conditions": [{'field': 'alert.event_source', 'value': ['bkmonitor'], 'method': 'neq', 'condition': 'and'}],
    }
    third_alert_rule.update(public_rule_info)
    AlertAssignRule.objects.create(**third_alert_rule)

    empty_user_assign_group = AlertAssignGroup.objects.create(
        priority=2, is_builtin=True, name="[内置]通知人为空默认规则组", bk_biz_id=bk_biz_id
    )
    empty_user_assign_rule = {
        "assign_group_id": empty_user_assign_group.id,
        "conditions": [
            {'field': 'alert.event_source', 'value': ['bkmonitor'], 'method': 'eq', 'condition': 'and'},
            {'field': 'is_empty_users', 'value': ['true'], 'method': 'eq', 'condition': 'and'},
        ],
    }
    empty_user_assign_rule.update(public_rule_info)
    AlertAssignRule.objects.create(**empty_user_assign_rule)
