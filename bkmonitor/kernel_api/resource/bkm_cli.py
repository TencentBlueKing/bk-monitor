"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

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

        # 服务桥出口统一 json-safe 归一：把所有 bkm_cli.* 函数的返回值过一遍
        # json.loads(json.dumps(result, default=str))，把 datetime / Decimal / lazy 等
        # 非 JSON-safe 对象转成字符串，再交给 ResponseSerializer 的 JSONField。
        # 为什么在出口统一做：commands.py:72 是同一类 bug 的逐函数补丁（diagnose_ts_metric_sync
        # 单独归一），但任何新增/已有 op 只要返回了非 JSON-safe 字段就会复发
        # （read-db-model 整行 datetime 序列化崩即是此因，报「result 值必须是有效 JSON」）。
        # 在服务桥唯一出口统一归一是根治：杜绝该类 bug 在任意 bkm_cli.* 函数处再复发。
        raw_result = KernelRPCRegistry.execute(op.func_name, params)
        result = json.loads(json.dumps(raw_result, default=str))

        return {
            "op_id": op.op_id,
            "func_name": op.func_name,
            "protocol": "bkm_cli_op_call",
            "result": result,
            "audit": {
                "capability_level": op.capability_level,
                "risk_level": op.risk_level,
                "requires_confirmation": op.requires_confirmation,
                "audit_tags": op.audit_tags,
            },
        }
