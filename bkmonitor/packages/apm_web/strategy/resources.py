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

from apm_web.container.helpers import ContainerHelper
from apm_web.handlers.host_handler import HostHandler


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
            query_string: str = f'target: "{app_name}:*" OR labels: "{ApmAlertHelper.format_app_label(app_name)}"'
        # 服务视角
        else:
            query_string = self._generate_service_perspective(
                bk_biz_id=validated_request_data["bk_biz_id"],
                app_name=app_name,
                service_name=service_name,
                target_types=validated_request_data["target_types"],
            )

        return {"query_string": query_string}

    @classmethod
    def _generate_service_perspective(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str,
        target_types: list[str],
    ) -> str:
        """生成服务视角的 query_string。

        按 target_types 路由，HOST / K8S-WORKLOAD 数据并发获取，按不同目标类型构建查询条件并以 OR 拼接。

        :param bk_biz_id: 业务 ID
        :param app_name: 应用名称
        :param service_name: 服务名称
        :param target_types: 目标类型列表
        :return: Lucene query_string
        """
        need_host: bool = EventTargetType.HOST in target_types
        need_k8s: bool = K8STargetType.WORKLOAD in target_types

        # 并发获取服务关联的 HOST / K8S-WORKLOAD 目标列表
        host_list: list[dict[str, Any]] = []
        workload_list: list[dict[str, Any]] = []
        if need_host or need_k8s:
            now: int = int(time.time())
            with ThreadPool() as pool:
                host_future = (
                    pool.apply_async(
                        HostHandler.list_application_hosts,
                        args=(bk_biz_id, app_name, service_name, now - 2 * 3600, now),
                    )
                    if need_host
                    else None
                )
                k8s_future = (
                    pool.apply_async(
                        ContainerHelper.get_service_related_k8s_targets,
                        args=(bk_biz_id, app_name, service_name),
                    )
                    if need_k8s
                    else None
                )
                if host_future:
                    host_list = host_future.get() or []
                if k8s_future:
                    workload_list = k8s_future.get() or []

        # 按目标类型构建查询条件
        conditions: list[str] = []
        for target_type in target_types:
            if target_type == APMTargetType.SERVICE:
                conditions.append(
                    f'target: "{app_name}:{service_name}" '
                    f'OR labels: ("{ApmAlertHelper.format_app_label(app_name)}"'
                    f' OR "{ApmAlertHelper.format_service_label(service_name)}")'
                )

            elif target_type == EventTargetType.HOST:
                host_parts: list[str] = [
                    f'"{host["bk_host_innerip"]}|{host["bk_cloud_id"]}"'
                    for host in host_list
                    if host.get("bk_host_innerip")
                ]
                if host_parts:
                    conditions.append(f"target: ({' OR '.join(host_parts)})")

            elif target_type == K8STargetType.WORKLOAD and workload_list:
                conditions.append(
                    " OR ".join(
                        f'(tags.bcs_cluster_id: "{w["bcs_cluster_id"]}"'
                        f' AND tags.namespace: "{w["namespace"]}"'
                        f' AND tags.workload_kind: "{w["workload_kind"]}"'
                        f' AND tags.workload_name: "{w["workload_name"]}")'
                        for w in workload_list
                    )
                )

        return " OR ".join(conditions)
