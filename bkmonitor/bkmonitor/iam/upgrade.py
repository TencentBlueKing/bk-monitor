# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
"""
权限升级
"""
import logging
from typing import List

from django.conf import settings

from bkmonitor.iam.action import _all_actions, ActionMeta
from bkmonitor.iam.resource import ResourceMeta, ResourceEnum
from core.drf_resource import api
from monitor_web.models.config import RolePermission


logger = logging.getLogger(__name__)


class UpgradeManager:
    def __init__(self):
        actions = list(_all_actions.values())
        # 读权限拥有的动作
        self.read_actions = [action for action in actions if action.related_resource_types and action.type == "view"]
        # 写权限拥有的动作
        self.write_actions = [action for action in actions if action.related_resource_types]
        # 超级管理员拥有的动作
        self.superuser_actions = actions

        # 业务列表
        biz_list = api.cmdb.get_business()
        self.biz_info = {business.bk_biz_id: business for business in biz_list}

    def list_upgrade_info(self):
        results = []

        bk_biz_ids = list(self.biz_info.keys())
        for bk_biz_id in bk_biz_ids:
            results.append(self.get_upgrade_info(bk_biz_id))

        return results

    def get_upgrade_info(self, bk_biz_id):

        if int(bk_biz_id) not in self.biz_info:
            raise ValueError(f"`bk_biz_id` ({bk_biz_id}) does not exist")

        business = self.biz_info[int(bk_biz_id)]

        role_permission_info = settings.DEFAULT_ROLE_PERMISSIONS.copy()
        rp_records = RolePermission.objects.filter(biz_id=business.bk_biz_id)
        for rp in rp_records:
            if rp.role in role_permission_info:
                role_permission_info[rp.role] = rp.permission

        users_with_write_permission = set()
        users_with_read_permission = set()

        for role_name, permission in role_permission_info.items():
            users = getattr(business, role_name, [])
            if permission == settings.ROLE_WRITE_PERMISSION:
                users_with_write_permission.update(users)
            else:
                users_with_read_permission.update(users)

        # 拥有写权限的用户，就一定有读权限，所以需要去重
        users_with_read_permission = users_with_read_permission - users_with_write_permission

        return {
            "bk_biz_id": business.bk_biz_id,
            "bk_biz_name": business.bk_biz_name,
            "users_with_write_permission": users_with_write_permission,
            "users_with_read_permission": users_with_read_permission,
        }

    def upgrade_by_business(self, bk_biz_id):

        upgrade_info = self.get_upgrade_info(bk_biz_id)

        instances = [{"id": str(upgrade_info["bk_biz_id"]), "name": upgrade_info["bk_biz_name"]}]

        # 写权限授权
        for user in upgrade_info["users_with_write_permission"]:
            self.grant_instance_permission(
                user=user, actions=self.write_actions, resource_meta=ResourceEnum.BUSINESS, instances=instances
            )
        # 读权限授权
        for user in upgrade_info["users_with_read_permission"]:
            self.grant_instance_permission(
                user=user, actions=self.read_actions, resource_meta=ResourceEnum.BUSINESS, instances=instances
            )

    def upgrade(self):
        bk_biz_ids = list(self.biz_info.keys())
        for bk_biz_id in bk_biz_ids:
            self.upgrade_by_business(bk_biz_id)

    def grant_instance_permission(
        self, user: str, actions: List[ActionMeta], resource_meta: ResourceMeta, instances: List
    ):
        """
        资源实例授权
        """
        params = {
            "no_request": True,
            "asynchronous": False,
            "operate": "grant",
            "system": settings.BK_IAM_SYSTEM_ID,
            "actions": [{"id": action.id} for action in actions],
            "subject": {"type": "user", "id": user},
            "resources": [{"system": resource_meta.system_id, "type": resource_meta.id, "instances": instances}],
        }
        try:
            result = api.iam.batch_instance(params)
        except Exception as e:
            print(f"[{user}] FAILED. Reason: {e}")
            return None
        else:
            print(f"[{user}]: SUCCESS.")
        return result
