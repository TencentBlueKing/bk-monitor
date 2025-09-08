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
cmdb接口缓存，celery定时任务
"""


from constants.data_source import LabelType
from core.drf_resource import api

list_result_table = {"api": api.metadata.list_result_table, "args": {}, "kwargs": {}}

list_bkdata_result_table = {"api": api.bkdata.list_result_table, "args": {}, "kwargs": {}}

query_event_group = {"api": api.metadata.query_event_group, "args": {}, "kwargs": {}}

get_label_api = {
    "api": api.metadata.get_label,
    "args": {},
    "kwargs": {"label_type": LabelType.ResultTableLabel, "include_admin_only": True},
}


def event_group_detail(bk_event_group_id):
    get_event_group = {"api": api.metadata.get_event_group, "args": {}, "kwargs": {"event_group_id": bk_event_group_id}}
    return get_event_group
