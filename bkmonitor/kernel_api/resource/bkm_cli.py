"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from core.drf_resource import Resource
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.tenant import inject_bk_tenant_id


class BkmCliOpCallResource(Resource):
    """
    bkm-cli 服务端 op 调用入口。

    请求侧只接受 op_id + params，客户端不能直接指定 func_name，避免绕过白名单。
    响应侧包含 func_name 以便客户端日志追踪和审计，op_id → func_name 映射由服务端白名单管控。
    """

    class RequestSerializer(serializers.Serializer):
        op_id = serializers.CharField(label="bkm-cli op id")
        params = serializers.DictField(required=False, default=dict, label="op 参数")

    class ResponseSerializer(serializers.Serializer):
        op_id = serializers.CharField(label="本次调用的 bkm-cli op id")
        func_name = serializers.CharField(label="op 映射到的 Kernel RPC 函数名")
        protocol = serializers.CharField(label="协议类型")
        result = serializers.JSONField(label="实际函数返回结果")
        audit = serializers.JSONField(label="op 审计元信息")

    def perform_request(self, validated_request_data):
        op = BkmCliOpRegistry.resolve(validated_request_data["op_id"])
        params = inject_bk_tenant_id(validated_request_data.get("params") or {})

        return {
            "op_id": op.op_id,
            "func_name": op.func_name,
            "protocol": "bkm_cli_op_call",
            "result": KernelRPCRegistry.execute(op.func_name, params),
            "audit": {
                "capability_level": op.capability_level,
                "risk_level": op.risk_level,
                "requires_confirmation": op.requires_confirmation,
                "audit_tags": op.audit_tags,
            },
        }
