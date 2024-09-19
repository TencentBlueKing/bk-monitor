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
from core.drf_resource import api


class RelationMetricHandler:
    """
    UnifyQuery Relation 指标辅助类
    """

    @classmethod
    def list_instances(cls, bk_biz_id, app_name, start_time, end_time, service_name=None):
        """从 relation 指标中获取实例"""

        params = {
            "bk_biz_ids": [bk_biz_id],
            "start_time": start_time,
            "end_time": end_time,
            "step": f"{end_time - start_time}s",
            "source_type": "apm_service",
            "target_type": "apm_service_instance",
            "source_info": {
                "apm_application_name": app_name,
                "apm_service_name": service_name,
            },
        }
        response = api.unify_query.query_multi_resource_range(**{"query_list": [params]})
        res = []
        for item in response.get("data", []):
            if item.get("code") != 200:
                continue

            for i in item.get("target_list", []):
                for j in i.get("items", []):
                    if j in res:
                        continue
                    res.append(j)

        return res
