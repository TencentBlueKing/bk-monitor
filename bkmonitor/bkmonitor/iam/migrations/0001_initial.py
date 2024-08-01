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
from iam.contrib.iam_migration.migrator import IAMMigrator
from iam.exceptions import AuthAPIError

from bkmonitor.iam.migrate import PolicyMigrator
from bkmonitor.migrate import BaseMigration


def migrate_iam(*args, **kwargs):
    pm = PolicyMigrator()

    # 如果存在view_business的权限，则需要进行旧版权限的迁移
    try:
        pm.query_polices_by_action_id("view_business")
        IAMMigrator("0001_legacy.json").migrate()
    except AuthAPIError as e:
        if "not found" not in str(e):
            raise e

    try:
        IAMMigrator("0001_initial.json").migrate()
    except AuthAPIError as e:
        # 已存在更新的权限，不需要再次迁移
        if "conflict" not in str(e):
            raise e


class Migration(BaseMigration):
    dependencies = []
    operations = [migrate_iam]
