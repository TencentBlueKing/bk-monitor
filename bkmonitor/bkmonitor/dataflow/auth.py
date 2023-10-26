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
