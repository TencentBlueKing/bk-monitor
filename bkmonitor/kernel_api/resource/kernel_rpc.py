"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from rest_framework import serializers

from core.drf_resource import Resource
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.tenant import inject_bk_tenant_id


class KernelRPCResource(Resource):
    """
    Kernel 类 RPC 通用入口

    请求参数仅包含 func_name 和 params。

    特殊协议：
    1. func_name = "__meta__", params.action = "list"
       返回可调用函数列表及简单说明
    2. func_name = "__meta__", params.action = "detail", params.target_func_name = "<函数名>"
       返回指定函数的详细说明

    普通调用：
    1. func_name = "<函数名>"
    2. params 为对应函数的入参字典
    3. 若未显式传入 bk_tenant_id，则会优先尝试基于 bk_biz_id / space_uid / table_id / bk_data_id /
       time_series_group_id 等标识反查唯一租户；若无法唯一确定，则由具体函数自行处理默认逻辑
    """

    class RequestSerializer(serializers.Serializer):
        func_name = serializers.CharField(label="要调用的函数名")
        params = serializers.DictField(required=False, default=dict, label="函数参数")

    class ResponseSerializer(serializers.Serializer):
        func_name = serializers.CharField(label="本次协议使用的函数名")
        protocol = serializers.CharField(label="协议类型")
        result = serializers.JSONField(label="协议返回结果")

    def perform_request(self, validated_request_data):
        func_name = validated_request_data["func_name"]
        params = validated_request_data.get("params") or {}

        if func_name == KernelRPCRegistry.META_PROTOCOL_FUNC_NAME:
            return {
                "func_name": func_name,
                "protocol": "meta",
                "result": self._handle_meta_protocol(params),
            }

        params = inject_bk_tenant_id(params)

        return {
            "func_name": func_name,
            "protocol": "call",
            "result": KernelRPCRegistry.execute(func_name, params),
        }

    def _handle_meta_protocol(self, params: dict[str, Any]) -> dict[str, Any]:
        action = params.get("action", KernelRPCRegistry.META_ACTION_LIST)

        if action == KernelRPCRegistry.META_ACTION_LIST:
            return {
                "protocols": [
                    {
                        "func_name": KernelRPCRegistry.META_PROTOCOL_FUNC_NAME,
                        "summary": "查询可调用函数列表及函数详细说明",
                    }
                ],
                "functions": KernelRPCRegistry.list_functions(),
            }

        if action == KernelRPCRegistry.META_ACTION_DETAIL:
            target_func_name = params.get("target_func_name")
            if not target_func_name:
                raise CustomException(message="params.target_func_name 为必填项")

            function_detail = KernelRPCRegistry.get_function_detail(target_func_name)
            if function_detail is None:
                raise CustomException(message=f"未找到函数详细说明: {target_func_name}")

            return {"function": function_detail}

        raise CustomException(
            message=(
                f"不支持的元协议动作: {action}，"
                f"仅支持 {KernelRPCRegistry.META_ACTION_LIST} 和 {KernelRPCRegistry.META_ACTION_DETAIL}"
            )
        )
