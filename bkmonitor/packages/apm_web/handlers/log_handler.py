# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import itertools

from apm_web.constants import DataStatus, ServiceRelationLogTypeChoices
from apm_web.models import LogServiceRelation
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import api


class ServiceLogHandler:
    """服务 - 日志工具类"""

    @classmethod
    def get_log_count_mapping(cls, bk_biz_id, app_name):
        """获取所有服务的关联日志的数据量"""

        # Step1: 找到此应用所有服务关联的日志
        service_mapping = {}
        relations = LogServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name)
        for i in relations:
            if i.log_type == ServiceRelationLogTypeChoices.BK_LOG:
                service_mapping[i.service_name] = {"bk_biz_id": i.related_bk_biz_id, "index_set_id": i.value}

        # Step2: 查询业务的所有索引集 (避免每个 relation 都单独查询)
        pool = ThreadPool()
        futures = []
        for i in {j["bk_biz_id"] for j in service_mapping.values()}:
            futures.append(pool.apply_async(api.log_search.search_index_set, kwds={"bk_biz_id": i}))
        index_set = list(itertools.chain(*[i.get() for i in futures]))

        # Step3: 根据 index_set_id 进行匹配
        res = {}
        for service_name, info in service_mapping.items():
            index_info = next((i for i in index_set if i.get("index_set_id") == int(info["index_set_id"])), None)
            if index_info:
                # tag_id == 4 为无数据 (bk_log 固定值)
                if all(i.get("tag_id") != 4 for i in index_info.get("tags", [])):
                    res[service_name] = DataStatus.NORMAL

        return res
