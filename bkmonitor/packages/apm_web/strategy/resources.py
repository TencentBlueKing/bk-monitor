"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.utils.thread_backend import ThreadPool
from constants.alert import APMTargetType, EventTargetType, K8STargetType
from constants.apm import ApmAlertHelper
from core.drf_resource import Resource

from apm_web.handlers.host_handler import HostHandler
from apm_web.strategy.dispatch.entity import EntitySet


class AlertBuiltinFilterResource(Resource):
    """APM 告警预设过滤条件。

    生成 APM 应用 / 服务视角的 Lucene query_string，供告警列表嵌入使用。
    """

    class RequestSerializer(serializers.Serializer):
        """告警预设过滤条件请求参数序列化器"""

        TARGET_TYPES: list[str] = [
            APMTargetType.SERVICE,
            EventTargetType.HOST,
            K8STargetType.WORKLOAD,
        ]

        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        app_name = serializers.CharField(label=_("应用名称"))
        service_name = serializers.CharField(label=_("服务名称"), required=False, default="", allow_blank=True)
        start_time = serializers.IntegerField(label=_("开始时间"), required=False, default=0)
        end_time = serializers.IntegerField(label=_("结束时间"), required=False, default=0)
        target_types = serializers.ListField(
            label=_("目标类型列表"),
            child=serializers.ChoiceField(choices=TARGET_TYPES),
            required=False,
            default=[APMTargetType.SERVICE],
        )

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        """获取告警预设过滤条件。

        根据是否传入 service_name 区分应用视角 / 服务视角，生成对应的 Lucene query_string。

        :param validated_request_data: 验证后的请求参数
        :return: 包含 query_string 的响应数据
        """
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]

        # 应用视角
        if not service_name:
            query_string: str = f'target: {app_name}\\:* OR labels: "{ApmAlertHelper.format_app_label(app_name)}"'
        # 服务视角
        else:
            query_string = self._generate_service_perspective(
                bk_biz_id=validated_request_data["bk_biz_id"],
                app_name=app_name,
                service_name=service_name,
                start_time=validated_request_data["start_time"],
                end_time=validated_request_data["end_time"],
                target_types=validated_request_data["target_types"],
            )

        return {"query_string": query_string}

    @classmethod
    def _build_apm_service_query_string(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        start_time: int,
        end_time: int,
    ) -> str:
        """构建 APM 服务目标类型的 query_string 片段。

        :param bk_biz_id: 业务 ID
        :param app_name: 应用名称
        :param service_name: 服务名称
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return: Lucene query_string 片段
        """
        return (
            f'target: "{app_name}:{service_name}" '
            f'OR labels: ("{ApmAlertHelper.format_app_label(app_name)}"'
            f' AND "{ApmAlertHelper.format_service_label(service_name)}")'
        )

    @classmethod
    def _build_host_query_string(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        start_time: int,
        end_time: int,
    ) -> str:
        """构建主机目标类型的 query_string 片段。

        :param bk_biz_id: 业务 ID
        :param app_name: 应用名称
        :param service_name: 服务名称
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return: Lucene query_string 片段，无关联主机时返回空字符串
        """
        host_list: list[dict[str, Any]] = (
            HostHandler.list_application_hosts(
                bk_biz_id,
                app_name,
                service_name,
                start_time,
                end_time,
            )
            or []
        )

        host_parts: list[str] = [
            f'"{host["bk_host_innerip"]}|{host["bk_cloud_id"]}"' for host in host_list if host.get("bk_host_innerip")
        ]
        if not host_parts:
            return ""

        return f"target: ({' OR '.join(host_parts)})"

    @classmethod
    def _build_workload_query_string(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        start_time: int,
        end_time: int,
    ) -> str:
        """构建 K8S 工作负载目标类型的 query_string 片段。

        :param bk_biz_id: 业务 ID
        :param app_name: 应用名称
        :param service_name: 服务名称
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return: Lucene query_string 片段，无关联负载时返回空字符串
        """
        workload_list: list[dict[str, Any]] = EntitySet.get_service_workloads(
            bk_biz_id,
            app_name,
            service_name,
        )
        if not workload_list:
            return ""

        return " OR ".join(
            f'(tags.bcs_cluster_id: "{w["bcs_cluster_id"]}"'
            f' AND tags.workload_kind: "{w["kind"]}"'
            f' AND tags.workload_name: "{w["name"]}")'
            for w in workload_list
        )

    @classmethod
    def _generate_service_perspective(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        start_time: int,
        end_time: int,
        target_types: list[str],
    ) -> str:
        """生成服务视角的 query_string。

        按 target_types 路由，通过 builder 注册表并发获取各目标类型的 query_string 片段，以 OR 拼接。

        :param bk_biz_id: 业务 ID
        :param app_name: 应用名称
        :param service_name: 服务名称
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param target_types: 目标类型列表
        :return: Lucene query_string
        """
        # 时间范围处理：未传入时使用默认值
        now: int = int(time.time())
        if not end_time:
            end_time = now
        if not start_time:
            start_time = end_time - 2 * 3600

        builder_register: dict[str, Any] = {
            APMTargetType.SERVICE: cls._build_apm_service_query_string,
            EventTargetType.HOST: cls._build_host_query_string,
            K8STargetType.WORKLOAD: cls._build_workload_query_string,
        }

        to_be_executed_builders = [builder_register[t] for t in target_types if t in builder_register]
        if not to_be_executed_builders:
            return ""

        pool = ThreadPool(len(to_be_executed_builders))
        results: list[str] = pool.map(
            lambda fn: fn(bk_biz_id, app_name, service_name, start_time, end_time),
            to_be_executed_builders,
        )
        pool.close()
        pool.join()

        conditions: list[str] = [f"({r})" for r in results if r]
        return " OR ".join(conditions)
