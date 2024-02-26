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

from typing import Optional

import six
from django.conf import settings
from django.utils.translation import ugettext as _
from rest_framework.exceptions import ValidationError

from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.models import UserGroup
from core.drf_resource import api


def create_default_notice_group(bk_biz_id: int, group_name=None) -> int:
    """
    获取或创建默认通知组
    :param group_name: 默认用户组名
    :param bk_biz_id: 业务ID
    :return: 通知组ID
    """
    default_group_names = [six.text_type(group["name"]) for group in settings.DEFAULT_NOTICE_GROUPS]
    if group_name not in default_group_names:
        # 不存在默认用第一个
        group_name = default_group_names[0]
    if not UserGroup.objects.filter(bk_biz_id=bk_biz_id, name=group_name).exists():
        for user_group in settings.DEFAULT_NOTICE_GROUPS:
            user_group_serializer = UserGroupDetailSlz(
                data={
                    "bk_biz_id": bk_biz_id,
                    "name": six.text_type(user_group["name"]),
                    "duty_arranges": [{"users": user_group["notice_receiver"]}],
                    "desc": user_group["message"],
                    "alert_notice": user_group["alert_notice"],
                    "action_notice": user_group["action_notice"],
                }
            )
            try:
                user_group_serializer.is_valid(True)
            except ValidationError:
                continue
            user_group_serializer.save()

    return UserGroup.objects.get(bk_biz_id=bk_biz_id, name=group_name).id


def _get_or_create_user_group(bk_biz_id, group_name, receivers):
    if not UserGroup.objects.filter(name=group_name, bk_biz_id=bk_biz_id).exists():
        user_group_serializer = UserGroupDetailSlz(
            data={
                "bk_biz_id": bk_biz_id,
                "name": group_name,
                "duty_arranges": [{"users": receivers}],
                "desc": settings.DEFAULT_NOTICE_GROUPS[0]["message"],
                "alert_notice": settings.DEFAULT_NOTICE_GROUPS[0]["alert_notice"],
                "action_notice": settings.DEFAULT_NOTICE_GROUPS[0]["action_notice"],
            }
        )
        user_group_serializer.is_valid(True)
        user_group_serializer.save()

    try:
        return UserGroup.objects.get(bk_biz_id=bk_biz_id, name=group_name).id
    except UserGroup.DoesNotExist:
        return None


def get_or_create_plugin_manager_group(bk_biz_id: int) -> Optional[int]:
    """
    获取或创建插件管理员组
    :param bk_biz_id: 业务ID
    """
    if getattr(settings, "OFFICIAL_PLUGINS_MANAGERS", ""):
        receivers = [{"type": "user", "id": user} for user in settings.OFFICIAL_PLUGINS_MANAGERS]
    else:
        blueking_maintainers = api.cmdb.get_business(all=True, bk_biz_ids=[api.cmdb.get_blueking_biz()])[
            0
        ].bk_biz_maintainer
        receivers = [{"type": "user", "id": user} for user in blueking_maintainers]

    return _get_or_create_user_group(bk_biz_id, _("【蓝鲸】官方插件管理员"), receivers)


def get_or_create_gse_manager_group(bk_biz_id: int) -> Optional[int]:
    """
    获取GSE 管理员通知组
    """
    if not getattr(settings, "GSE_MANAGERS", ""):
        return None
    receivers = [{"type": "user", "id": user} for user in settings.GSE_MANAGERS]

    return _get_or_create_user_group(bk_biz_id, _("【蓝鲸】GSE管理员"), receivers)


def get_or_create_ops_notice_group(bk_biz_id: int) -> Optional[int]:
    """
    获取或创建运维通知组
    :param bk_biz_id: 业务ID
    """
    # 获得内置的运维告警组配置
    user_group = settings.DEFAULT_NOTICE_GROUPS[1]
    # 判断业务下的告警组是否已经创建
    if not UserGroup.objects.filter(bk_biz_id=bk_biz_id, name=six.text_type(user_group["name"])).exists():
        user_group_serializer = UserGroupDetailSlz(
            data={
                "bk_biz_id": bk_biz_id,
                "name": six.text_type(user_group["name"]),
                "duty_arranges": [{"users": user_group["notice_receiver"]}],
                "desc": user_group["message"],
                "alert_notice": user_group["alert_notice"],
                "action_notice": user_group["action_notice"],
            }
        )
        user_group_serializer.is_valid(True)
        user_group_serializer.save()

    return UserGroup.objects.get(bk_biz_id=bk_biz_id, name=six.text_type(user_group["name"])).id


def add_member_to_collecting_notice_group(bk_biz_id: int, user_id: str) -> int:
    """创建采集负责人"""
    collecting_group_name = _("采集负责人")
    instances = UserGroup.objects.filter(bk_biz_id=bk_biz_id, name=collecting_group_name)
    if not instances.exists():
        user_group = {
            "name": collecting_group_name,
            "notice_receiver": [{"id": user_id, "type": "user"}],
            **settings.PUBLIC_NOTICE_CONFIG,
        }
        user_group_serializer = UserGroupDetailSlz(
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
        inst = instances[0]
        duty_arranges = UserGroupDetailSlz(inst).data["duty_arranges"]
        # 目前按照《直接通知》方式进行判定和添加成员
        current_users = duty_arranges[0]["users"]
        for user in current_users:
            if user["type"] == "user" and user["id"] == user_id:
                return inst.id
        current_users.append({"id": user_id, "type": "user"})
        user_group_serializer = UserGroupDetailSlz(
            inst, data={"duty_arranges": [{"users": current_users}]}, partial=True
        )

    user_group_serializer.is_valid(True)
    inst = user_group_serializer.save()
    return inst.id
