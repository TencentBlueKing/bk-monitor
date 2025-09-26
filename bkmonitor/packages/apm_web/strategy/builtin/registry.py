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

import six

from typing import Any
from django.utils import timezone

from . import rpc, metric, base
from .. import constants

from apm_web.models import Application
from apm_web.models.strategy import StrategyTemplate

from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.models import UserGroup
from constants.alert import PUBLIC_NOTICE_CONFIG
from django.utils.translation import gettext_lazy as _


class BuiltinStrategyTemplateRegistry:
    _BUILTIN_STRATEGY_TEMPLATES: list[base.StrategyTemplateSet] = [
        rpc.RPCStrategyTemplateSet,
        metric.MetricStrategyTemplateSet,
    ]

    def __init__(self, application: Application) -> None:
        self.app_name: str = application.app_name
        self.bk_biz_id: int = application.bk_biz_id
        self.application: Application = application

    @classmethod
    def _add_member_to_notice_group(
        cls, bk_biz_id: int, user_ids: list[str], group_name: str, notice_ways: list[str] | None = None
    ) -> int:
        """增加成员到告警组，告警组不存在时默认创建
        :param bk_biz_id: 业务 ID
        :param user_ids: 用户 ID 列表
        :param group_name: 告警组名称
        :param notice_ways: 通知方式
        :return:
        """
        user_ids: set[str] = set(user_ids)
        user_group_inst: UserGroup | None = UserGroup.objects.filter(bk_biz_id=bk_biz_id, name=group_name).first()
        if user_group_inst is None:
            notice_config: dict[str, Any] = copy.deepcopy(PUBLIC_NOTICE_CONFIG)
            for notice_way_config in (
                notice_config["alert_notice"][0]["notify_config"] + notice_config["action_notice"][0]["notify_config"]
            ):
                notice_way_config["type"] = notice_ways or ["rtx"]

            user_group: dict[str, Any] = {
                "name": group_name,
                "notice_receiver": [{"id": user_id, "type": "user"} for user_id in set(user_ids)],
                **notice_config,
            }
            user_group_serializer: UserGroupDetailSlz = UserGroupDetailSlz(
                data={
                    "bk_biz_id": bk_biz_id,
                    "name": six.text_type(user_group["name"]),
                    "duty_arranges": [{"users": user_group["notice_receiver"]}],
                    "desc": user_group["message"],
                    "alert_notice": user_group["alert_notice"],
                    "action_notice": user_group["action_notice"],
                }
            )
        else:
            # 检索用户是否已经存在在当前告警组，存在则跳过添加步骤
            duty_arranges: list[dict[str, Any]] = UserGroupDetailSlz(user_group_inst).data["duty_arranges"]
            current_users: list[dict[str, Any]] = duty_arranges[0]["users"]
            to_be_add_user_ids: set[str] = user_ids - {user["id"] for user in current_users if user["type"] == "user"}
            if not to_be_add_user_ids:
                return user_group_inst.id

            current_users.extend([{"id": user_id, "type": "user"} for user_id in to_be_add_user_ids])
            user_group_serializer = UserGroupDetailSlz(
                user_group_inst, data={"duty_arranges": [{"users": current_users}]}, partial=True
            )

        user_group_serializer.is_valid(raise_exception=True)
        return user_group_serializer.save().id

    @classmethod
    def apply_default_notice_group(cls, application: Application) -> int:
        """为应用创建默认的告警组，并更新通知人。
        :param application: APM 应用
        :return:
        """
        return cls._add_member_to_notice_group(
            bk_biz_id=application.bk_biz_id,
            user_ids=[application.update_user, application.create_user],
            group_name=str(_("【APM】{app_name} 告警组".format(app_name=application.app_name))),
        )

    def register(self):
        """注册内置告警策略模板"""

        # 创建/更新默认告警组
        user_group_id: int = self.apply_default_notice_group(self.application)

        # TODO 识别应用的框架、语言，再决定注册哪些内置模板。
        systems: list[str] = [builtin.SYSTEM.value for builtin in self._BUILTIN_STRATEGY_TEMPLATES]
        tmpl_code__id_map: dict[str, int] = {
            tmpl["code"]: tmpl["id"]
            for tmpl in StrategyTemplate.origin_objects.filter(bk_biz_id=self.bk_biz_id, system__in=systems).values(
                "code", "id"
            )
        }

        to_be_created: list[StrategyTemplate] = []
        to_be_updated: list[StrategyTemplate] = []
        local_tmpl_codes: set[str] = set()
        remote_tmpl_codes: set[str] = set(tmpl_code__id_map.keys())
        for builtin in self._BUILTIN_STRATEGY_TEMPLATES:
            for template in builtin.STRATEGY_TEMPLATES:
                # TODO 开放配置项，允许根据应用场景，内置更多模板。
                if template["code"] not in builtin.ENABLED_CODES:
                    continue

                obj: StrategyTemplate = StrategyTemplate(
                    **template,
                    user_group_ids=[user_group_id],
                    type=constants.StrategyTemplateType.BUILTIN_TEMPLATE.value,
                )
                obj.bk_biz_id, obj.app_name, obj.system = self.bk_biz_id, self.app_name, builtin.SYSTEM.value
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

        if to_be_created:
            StrategyTemplate.objects.bulk_create(to_be_created)
        if to_be_updated:
            StrategyTemplate.objects.bulk_update(
                to_be_updated,
                fields=[
                    "name",
                    "type",
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
            StrategyTemplate.origin_objects.filter(bk_biz_id=self.bk_biz_id, code__in=to_be_deleted).update(
                is_deleted=True
            )
