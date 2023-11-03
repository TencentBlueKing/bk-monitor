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
import json

from iam.contrib.iam_migration.migrator import IAMMigrator
from iam.exceptions import AuthAPIError

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.migrate import PolicyMigrator
from bkmonitor.migrate import BaseMigration
from bkmonitor.utils.thread_backend import ThreadPool


def migrate_dashboard_permission():
    """
    迁移仪表盘权限
    """
    print("start migrate dashboard permission")

    pm = PolicyMigrator()

    # 如果旧版权限不存在，则不需要迁移
    try:
        manage_policies = pm.query_polices_by_action_id("manage_dashboard_v2")
        view_policies = pm.query_polices_by_action_id("view_dashboard_v2")
    except AuthAPIError as e:
        if "not found" not in str(e):
            raise e
        print("manage_dashboard_v2 or view_dashboard_v2 not found, skip migrate dashboard permission")
        # 新版权限初始化
        IAMMigrator("0002_initial.json").migrate()
        return

    # 旧版权限改名
    IAMMigrator("0002_legacy.json").migrate()
    IAMMigrator("0002_initial.json").migrate()

    resources = []
    for policy in manage_policies:
        resources.append(pm.policy_to_resource(ActionEnum.EDIT_SINGLE_DASHBOARD, policy))
        resources.append(pm.policy_to_resource(ActionEnum.NEW_DASHBOARD, policy))

    for policy in view_policies:
        resource = pm.policy_to_resource(ActionEnum.VIEW_SINGLE_DASHBOARD, policy)
        resources.append(resource)

    futures = []

    # 并发请求
    if resources:
        pool = ThreadPool(30)
        for resource in resources:
            futures.append((pool.apply_async(pm.grant_resource, args=(resource,)), resource))
        pool.close()
        pool.join()

    results = []
    for future, resource in futures:
        try:
            results.append(future.get())
        except Exception as e:
            print(
                "[grant_resource] grant permission for resource: {}, something wrong: {}".format(
                    json.dumps(resource), e
                )
            )

    print("migrate dashboard permission finished")


class Migration(BaseMigration):
    dependencies = ["0001_initial"]
    operations = [migrate_dashboard_permission]
