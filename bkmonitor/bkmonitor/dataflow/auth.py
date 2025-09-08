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

import json
import logging
from typing import List

from django.conf import settings

from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger("bkmonitor.dataflow")


def check_has_permission(project_id, rt_id):
    # 1. 效验表是否有权限
    try:
        has_permission = api.bkdata.auth_projects_data_check(project_id=project_id, result_table_id=rt_id)
    except BKAPIError:
        logger.exception(
            "check whether the project({}) has the permission of ({}) table, error.".format(project_id, rt_id)
        )
        return False

    return has_permission


def ensure_has_permission_with_rt_id(bk_username, rt_id, project_id=None):
    project_id = project_id or settings.BK_DATA_PROJECT_ID
    if not check_has_permission(project_id, rt_id):
        try:
            # 针对结果表直接授权给项目
            result = api.bkdata.auth_result_table(
                project_id=project_id, object_id=rt_id, bk_biz_id=int(rt_id.split("_")[0])
            )
            # 授权给某个项目
            # result = api.bkdata.auth_tickets(
            #     **{
            #         "bk_username": bk_username,
            #         "ticket_type": "project_biz",
            #         "permissions": [
            #             {
            #                 "subject_id": project_id,
            #                 "subject_name": "蓝鲸监控-异常检测模型",
            #                 "subject_class": "project",
            #                 "action": "result_table.query_data",
            #                 "object_class": "result_table",
            #                 "scope": {"result_table_id": rt_id},
            #             }
            #         ],
            #         "reason": "蓝鲸监控平台统一授权",
            #     }
            # )
        except Exception:  # noqa
            logger.exception("failed to grant permission({})".format(rt_id))
            return False
        logger.info("grant permission successfully(%s), result:%s", rt_id, result)

    return True


def batch_add_permission(project_id: int, bk_biz_id: int, table_id_list: List) -> bool:
    """批量检查项目是否有结果表的权限"""
    project_id = project_id or settings.BK_DATA_PROJECT_ID
    # 如果检测异常，则全量再授权一次
    try:
        table_id_perm = api.bkdata.query_auth_projects_data(project_id=project_id, object_ids=table_id_list)
        need_auth_table_id_list = table_id_perm.get("no_permissions") or []
    except BKAPIError as e:
        logger.error(
            "check whether the project: %s has the permission of %s table, error: %s",
            project_id,
            json.dumps(table_id_list),
            e,
        )
        need_auth_table_id_list = table_id_list
    if not need_auth_table_id_list:
        return True
    # 授权结果表
    try:
        api.bkdata.batch_auth_result_table(
            project_id=project_id, object_ids=need_auth_table_id_list, bk_biz_id=bk_biz_id
        )
    except BKAPIError as e:
        logger.error(
            "add project: %s prem to access table: %s error: %s", project_id, json.dumps(need_auth_table_id_list), e
        )
        return False

    return True
