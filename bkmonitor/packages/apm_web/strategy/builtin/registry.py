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


import logging

from django.db.models import QuerySet, Q
from django.utils import timezone
from django.utils.functional import cached_property

from . import serializers, templates

from apm_web.models import Application, StrategyTemplate, StrategyInstance

from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.models import UserGroup
from constants.alert import PUBLIC_NOTICE_CONFIG
from django.utils.translation import gettext_lazy as _

from .. import dispatch, constants


logger = logging.getLogger(__name__)


class BuiltinStrategyTemplateRegistry:
    # 内置策略模板版本，用于定时任务执行时，判断是否需要执行。
    # 如果更新了内置策略模板，需要更新该版本号。
    BUILTIN_STRATEGY_TEMPLATE_VERSION = "1.0.0"

    _BUILTIN_STRATEGY_TEMPLATES: list[type[templates.StrategyTemplateSet]] = templates.BUILTIN_STRATEGY_TEMPLATE

    def __init__(self, application: Application) -> None:
        self.app_name: str = application.app_name
        self.bk_biz_id: int = application.bk_biz_id
        self.application: Application = application

    def is_need_register(self, app_applied_version: str, applied_systems: list[str]) -> bool:
        """判断是否需要注册内置策略模板"""
        is_version_update = app_applied_version != self.BUILTIN_STRATEGY_TEMPLATE_VERSION
        is_system_update = set(applied_systems) != set(self.systems)
        return is_version_update or is_system_update

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

    def _get_strategy_template_qs(self, only_builtin: bool = False) -> QuerySet[StrategyTemplate]:
        qs: QuerySet[StrategyTemplate] = StrategyTemplate.origin_objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name
        )
        if only_builtin:
            qs = qs.filter(type=constants.StrategyTemplateType.BUILTIN_TEMPLATE.value)
        return qs

    @cached_property
    def _supported_builtin_templ_sets(self) -> list[type[templates.StrategyTemplateSet]]:
        supported_systems: list[str] = dispatch.SystemChecker(
            dispatch.EntitySet(self.bk_biz_id, self.app_name)
        ).check_systems()

        return [builtin for builtin in self._BUILTIN_STRATEGY_TEMPLATES if builtin.SYSTEM.value in supported_systems]

    @cached_property
    def systems(self) -> list[str]:
        return [builtin.SYSTEM.value for builtin in self._supported_builtin_templ_sets]

    def register(self):
        """注册内置告警策略模板"""

        if not self.systems:
            logger.info(
                "[BuiltinStrategyTemplateRegistry] no supported system, skip register: bk_biz_id=%s, app_name=%s",
                self.bk_biz_id,
                self.app_name,
            )
            return

        logger.info(
            "[BuiltinStrategyTemplateRegistry] start register: bk_biz_id=%s, app_name=%s, systems=%s",
            self.bk_biz_id,
            self.app_name,
            self.systems,
        )

        # 创建/更新默认告警组
        user_group_id: int = self.apply_default_notice_group(self.application)

        code_tmpl_map: dict[str, dict[str, Any]] = {
            tmpl["code"]: tmpl
            for tmpl in self._get_strategy_template_qs(only_builtin=True)
            .filter(system__in=self.systems)
            .values("code", "id", "update_user")
        }

        to_be_created: list[StrategyTemplate] = []
        to_be_updated: list[StrategyTemplate] = []
        local_tmpl_codes: set[str] = set()
        remote_tmpl_codes: set[str] = set(code_tmpl_map.keys())
        for builtin in self._supported_builtin_templ_sets:
            for template in builtin.STRATEGY_TEMPLATES:
                # TODO 开放配置项，允许根据应用场景，内置更多模板。
                if template["code"] not in builtin.ENABLED_CODES:
                    continue
                s = serializers.BuiltinStrategyTemplateSerializer(
                    data={
                        **template,
                        "user_group_ids": [user_group_id],
                        "bk_biz_id": self.bk_biz_id,
                        "app_name": self.app_name,
                        "system": builtin.SYSTEM.value,
                    }
                )
                s.is_valid(raise_exception=True)
                obj: StrategyTemplate = StrategyTemplate(**s.validated_data)
                if obj.code not in code_tmpl_map:
                    to_be_created.append(obj)
                # 被用户更新过的，不再进行更新
                elif obj.code in code_tmpl_map and code_tmpl_map[obj.code]["update_user"] == obj.update_user:
                    obj.update_time = timezone.now()
                    obj.pk = code_tmpl_map[obj.code]["id"]
                    to_be_updated.append(obj)
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
                    "update_time",
                ],
            )

        to_be_deleted: set[int] = {code_tmpl_map[code]["id"] for code in list(remote_tmpl_codes - local_tmpl_codes)}
        if not to_be_deleted:
            logger.info(
                "[BuiltinStrategyTemplateRegistry] finish register: "
                "bk_biz_id=%s, app_name=%s, to_be_created=%s, to_be_updated=%s",
                self.bk_biz_id,
                self.app_name,
                len(to_be_created),
                len(to_be_updated),
            )
            return

        # 模板已下发或被克隆（且副本没有被删除）时，不再删除。
        has_been_cloned: set[int] = set(
            self._get_strategy_template_qs()
            .filter(root_id__in=to_be_deleted, is_deleted=False)
            .values_list("root_id", flat=True)
        )
        has_been_applied: set[int] = set(
            StrategyInstance.objects.filter(strategy_template_id__in=to_be_deleted).values_list(
                "strategy_template_id", flat=True
            )
        )
        need_to_delete: set[int] = to_be_deleted - has_been_cloned - has_been_applied
        logger.info(
            "[BuiltinStrategyTemplateRegistry] handle delete: bk_biz_id=%s, app_name=%s, "
            "to_be_deleted=%s, has_been_cloned=%s, has_been_applied=%s, need_to_delete=%s",
            self.bk_biz_id,
            self.app_name,
            to_be_deleted,
            has_been_cloned,
            has_been_applied,
            need_to_delete,
        )

        if need_to_delete:
            self._get_strategy_template_qs().filter(Q(id__in=need_to_delete) | Q(root_id__in=need_to_delete)).delete()

        logger.info(
            "[BuiltinStrategyTemplateRegistry] finish register: "
            "bk_biz_id=%s, app_name=%s, to_be_created=%s, to_be_updated=%s, need_to_delete=%s",
            self.bk_biz_id,
            self.app_name,
            len(to_be_created),
            len(to_be_updated),
            len(need_to_delete),
        )
