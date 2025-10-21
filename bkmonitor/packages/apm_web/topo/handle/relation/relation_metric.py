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
from apm_web.constants import TopoNodeKind
from apm_web.handlers.service_handler import ServiceHandler
from core.drf_resource import api


class RelationMetricHandler:
    """
    UnifyQuery Relation 指标辅助类
    """

    @classmethod
    def list_instances(cls, bk_biz_id, app_name, start_time, end_time, service_name=None, filter_component=False):
        """从 relation 指标中获取实例"""
        source_params = {"apm_application_name": app_name}
        if service_name:
            source_params["apm_service_name"] = service_name
        params = {
            "bk_biz_ids": [bk_biz_id],
            "start_time": start_time,
            "end_time": end_time,
            "step": f"{end_time - start_time}s",
            "source_type": "apm_service",
            "target_type": "apm_service_instance",
            "source_info": source_params,
        }
        response = api.unify_query.query_multi_resource_range(**{"query_list": [params]})
        res = []

        for item in response.get("data", []):
            if item.get("code") != 200:
                continue

            for i in item.get("target_list", []):
                for j in i.get("items", []):
                    instance = {"apm_service_instance_name": j["apm_service_instance_name"]}
                    if instance in res:
                        continue
                    if not service_name and filter_component:
                        # 过滤掉组件服务产生的实例
                        service_info = ServiceHandler.get_node(
                            bk_biz_id,
                            app_name,
                            j["apm_service_name"],
                            raise_exception=False,
                        )
                        if not service_info or service_info.get("extra_data", {}).get("kind") != TopoNodeKind.SERVICE:
                            continue

                    res.append(instance)

        return res
