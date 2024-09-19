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
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.service_handler import ServiceHandler


class CompatibleQuery:
    """兼容组件类服务、自定义服务的查询条件 统一获取"""

    @classmethod
    def get_alert_query_string(cls, table_id, bk_biz_id, app_name, service_name=None, endpoint_name=None):
        """[获取告警查询语句]"""
        res = f"metric: custom.{table_id}.*"
        if not service_name:
            return res

        try:
            node = ServiceHandler.get_node(bk_biz_id, app_name, service_name, raise_exception=False)
            if ComponentHandler.is_component_by_node(node):
                query = (
                    f'tags.{ComponentHandler.get_dimension_key(node)}: '
                    f'"{node["extra_data"]["predicate_value"]}" AND '
                    f'tags.service_name: "{ComponentHandler.get_component_belong_service(service_name)}"'
                )
            elif ServiceHandler.is_remote_service_by_node(node):
                query = f'tags.peer_service: "{ServiceHandler.get_remote_service_origin_name(service_name)}"'
            else:
                query = f'tags.service_name: "{service_name}"'
        except ValueError:
            query = f'tags.service_name: "{service_name}"'

        if endpoint_name:
            query += f' AND tags.span_name: "{endpoint_name}"'

        return f"{res} AND {query}"

    @classmethod
    def list_metric_wheres(cls, bk_biz_id, app_name, service_name=None, endpoint_name=None):
        """[获取 collector 内置 APM 指标的 where 条件列表]"""
        if not service_name:
            return []

        node = ServiceHandler.get_node(bk_biz_id, app_name, service_name, raise_exception=False)

        if ComponentHandler.is_component_by_node(node):
            wheres = [
                {
                    "key": ComponentHandler.get_dimension_key(node),
                    "method": "eq",
                    "value": [node["extra_data"]["predicate_value"]],
                },
                {
                    "key": "service_name",
                    "method": "eq",
                    "value": [ComponentHandler.get_component_belong_service(service_name)],
                },
            ]
        elif ServiceHandler.is_remote_service_by_node(node):
            wheres = [
                {
                    "key": "peer_service",
                    "method": "eq",
                    "value": [ServiceHandler.get_remote_service_origin_name(service_name)],
                }
            ]
        else:
            wheres = [{"key": "service_name", "method": "eq", "value": [service_name]}]

        if endpoint_name:
            wheres.append({"key": "span_name", "method": "eq", "value": [endpoint_name]})

        return wheres

    @classmethod
    def list_flow_metric_wheres(cls, mode, service_name=None):
        """[获取 flow 指标的 where 条件列表]"""
        if mode not in ["full", "caller", "callee"]:
            raise ValueError(f"mode: {mode} not supported")

        if not service_name:
            return []

        if mode == "full":
            wheres = [
                {"key": "from_apm_service_name", "method": "eq", "value": [service_name]},
                {"condition": "or", "key": "to_apm_service_name", "method": "eq", "value": [service_name]},
            ]
        elif mode == "caller":
            wheres = [{"key": "from_apm_service_name", "method": "eq", "value": [service_name]}]
        else:
            wheres = [{"key": "to_apm_service_name", "method": "eq", "value": [service_name]}]

        return wheres
