"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time

from celery import shared_task
from django.utils.translation import gettext as _

from bkmonitor.models import ActionConfig, AlertAssignGroup, AlertAssignRule
from core.drf_resource import api, resource
from fta_web.constants import QuickSolutionsConfig
from monitor_web.strategies.user_groups import create_default_notice_group

logger = logging.getLogger("celery")


@shared_task(ignore_result=True)
def update_home_statistics():
    # 更新首页的统计数据
    for days in [1, 7, 15, 30]:
        start_time = time.time()
        resource.home.all_biz_statistics.request.refresh(days=days)
        end_time = time.time()
        logger.info("[update_home_statistics] refresh %s days data in %ss", days, end_time - start_time)


@shared_task(ignore_result=True)
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
            api.sops.import_project_template(bk_biz_id=bk_biz_id, project_id=bk_biz_id, template_data=template_data)
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
                "is_enabled": True,
                "action_type": "notice",
                "upgrade_config": {"is_enabled": False, "user_groups": [], "upgrade_interval": 0},
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
        "conditions": [{"field": "alert.event_source", "value": ["bkmonitor"], "method": "neq", "condition": "and"}],
    }
    third_alert_rule.update(public_rule_info)
    AlertAssignRule.objects.create(**third_alert_rule)

    empty_user_assign_group = AlertAssignGroup.objects.create(
        priority=2, is_builtin=True, name="[内置]通知人为空默认规则组", bk_biz_id=bk_biz_id
    )
    empty_user_assign_rule = {
        "assign_group_id": empty_user_assign_group.id,
        "conditions": [
            {"field": "alert.event_source", "value": ["bkmonitor"], "method": "eq", "condition": "and"},
            {"field": "is_empty_users", "value": ["true"], "method": "eq", "condition": "and"},
        ],
    }
    empty_user_assign_rule.update(public_rule_info)
    AlertAssignRule.objects.create(**empty_user_assign_rule)
