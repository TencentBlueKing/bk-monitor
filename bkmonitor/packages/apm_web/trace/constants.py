"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from enum import Enum

from django.utils.translation import gettext_lazy as _

from constants.elasticsearch import QueryStringOperators


class EnabledStatisticsDimension(Enum):
    """
    开启字段分析的维度类型枚举（映射到 Elasticsearch 数据类型）
    """

    KEYWORD = "keyword"
    INTEGER = "integer"
    LONG = "long"
    DOUBLE = "double"


class OperatorEnum:
    """操作符枚举"""

    class OperatorOptions:
        """操作符选项"""

        IS_WILDCARD = {"label": _("使用通配符"), "name": "is_wildcard", "default": False}
        GROUP_RELATION = {
            "label": _("组间关系"),
            "name": "group_relation",
            "default": "OR",
            "children": [
                {"label": "AND", "value": "AND"},
                {"label": "OR", "value": "OR"},
            ],
        }

    EXISTS = {"operator": "exists", "label": _("存在"), "placeholder": _("确认字段已存在")}
    NOT_EXISTS = {"operator": "not exists", "label": _("不存在"), "placeholder": _("确认字段不存在")}
    EQUAL = {"operator": "equal", "label": "=", "placeholder": _("请选择或直接输入，Enter分隔")}
    NOT_EQUAL = {"operator": "not_equal", "label": "!=", "placeholder": _("请选择或直接输入，Enter分隔")}
    LIKE = {"operator": "like", "label": _("包含"), "placeholder": _("请选择或直接输入，Enter分隔")}
    NOT_LIKE = {"operator": "not_like", "label": _("不包含"), "placeholder": _("请选择或直接输入，Enter分隔")}
    GT = {"operator": "gt", "label": ">", "placeholder": _("请选择或直接输入")}
    LT = {"operator": "lt", "label": "<", "placeholder": _("请选择或直接输入")}
    GTE = {"operator": "gte", "label": ">=", "placeholder": _("请选择或直接输入")}
    LTE = {"operator": "lte", "label": "<=", "placeholder": _("请选择或直接输入")}

    LIKE_WILDCARD = {
        "operator": "like",
        "label": _("包含"),
        "placeholder": _("请选择或直接输入，Enter分隔"),
        "options": [OperatorOptions.IS_WILDCARD, OperatorOptions.GROUP_RELATION],
    }
    NOT_LIKE_WOLDCARD = {
        "operator": "not_like",
        "label": _("不包含"),
        "placeholder": _("请选择或直接输入，Enter分隔"),
        "options": [OperatorOptions.IS_WILDCARD, OperatorOptions.GROUP_RELATION],
    }

    QueryStringOperatorMapping = {
        EXISTS["operator"]: QueryStringOperators.EXISTS,
        NOT_EXISTS["operator"]: QueryStringOperators.NOT_EXISTS,
        EQUAL["operator"]: QueryStringOperators.EQUAL,
        NOT_EQUAL["operator"]: QueryStringOperators.NOT_EQUAL,
        LIKE["operator"]: QueryStringOperators.INCLUDE,
        NOT_LIKE["operator"]: QueryStringOperators.NOT_INCLUDE,
        GT["operator"]: QueryStringOperators.GT,
        LT["operator"]: QueryStringOperators.LT,
        GTE["operator"]: QueryStringOperators.GTE,
        LTE["operator"]: QueryStringOperators.LTE,
        "between": QueryStringOperators.BETWEEN,
    }


OPERATORS = {
    "keyword": [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
        OperatorEnum.LIKE,
        OperatorEnum.NOT_LIKE,
    ],
    "text": [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.LIKE_WILDCARD,
        OperatorEnum.NOT_LIKE_WOLDCARD,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "integer": [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "long": [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "double": [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "date": [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "boolean": [OperatorEnum.EQUAL, OperatorEnum.NOT_EQUAL, OperatorEnum.EXISTS, OperatorEnum.NOT_EXISTS],
    "conflict": [
        OperatorEnum.EQUAL,
        OperatorEnum.NOT_EQUAL,
        OperatorEnum.GT,
        OperatorEnum.GTE,
        OperatorEnum.LT,
        OperatorEnum.LTE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
}


TRACE_FIELD_ALIAS = {
    # Trace 视角
    "hierarchy_count": _("Span 层数"),
    "service_count": _("服务数量"),
    "span_count": _("Span 数量"),
    "root_service": _("入口服务"),
    "root_service_span_id": _("入口服务 Span ID"),
    "root_service_span_name": _("入口服务接口"),
    "root_service_status_code": _("入口服务状态码"),
    "root_service_category": _("入口服务分类"),
    "root_service_kind": _("入口服务类型"),
    "root_span_id": _("根 Span ID"),
    "root_span_name": _("根 Span 接口"),
    "root_span_service": _("根 Span 服务"),
    "root_span_kind": _("根 Span 类型"),
    "error": _("是否错误"),
    "error_count": _("错误数量"),
    "min_start_time": _("开始时间"),
    "max_end_time": _("结束时间"),
    "trace_duration": _("耗时"),
    "span_max_duration": _("最大 Span 耗时"),
    "span_min_duration": _("最小 Span 耗时"),
    "category_statistics.async_backend": _("Async 后台数量"),
    "category_statistics.db": _("DB 数量"),
    "category_statistics.http": _("HTTP 数量"),
    "category_statistics.messaging": _("Messaging 数量"),
    "category_statistics.other": _("Other 数量"),
    "category_statistics.rpc": _("RPC 数量"),
    "kind_statistics.async": _("异步调用数量"),
    "kind_statistics.interval": _("内部调用数量"),
    "kind_statistics.sync": _("同步调用数量"),
    "kind_statistics.unspecified": _("未知调用数量"),
    # Span 视角
    "elapsed_time": _("耗时"),
    "end_time": _("结束时间"),
    "kind": _("类型"),
    "links": _("关联信息"),
    "parent_span_id": _("父 Span ID"),
    "span_id": "Span ID",
    "span_name": _("接口名称"),
    "start_time": _("开始时间"),
    "time": _("时间"),
    "trace_id": "Trace ID",
    "trace_state": _("Trace 状态"),
    "attributes.apdex_type": "",
    "attributes.http.host": "HTTP Host",
    "attributes.http.url": "HTTP URL",
    "attributes.server.address": _("服务地址"),
    "attributes.http.scheme": _("HTTP协议"),
    "attributes.http.flavor": _("HTTP服务名称"),
    "attributes.http.route": "",
    "attributes.http.server_name": "",
    "attributes.http.target": "",
    "attributes.http.method": _("HTTP 方法"),
    "attributes.http.status_code": _("HTTP 状态码"),
    "attributes.rpc.method": _("RPC 方法"),
    "attributes.rpc.service": _("RPC 服务"),
    "attributes.rpc.system": _("RPC 系统名"),
    "attributes.rpc.grpc.status_code": _("gRPC 状态码"),
    "attributes.db.name": _("DB 名称"),
    "attributes.db.operation": _("DB 操作"),
    "attributes.db.system": _("DB 类型"),
    "attributes.db.statement": _("DB 语句"),
    "attributes.db.instance": _("DB 实例"),
    "attributes.messaging.system": _("消息系统"),
    "attributes.messaging.destination": _("消息目的地"),
    "attributes.messaging.destination_kind": _("消息目的地类型"),
    "attributes.celery.action": _("操作名称"),
    "attributes.celery.task_name": _("任务名称"),
    "attributes.http.user_agent": _("HTTP 代理"),
    "attributes.net.host.name": _("本机名称"),
    "attributes.net.host.port": _("本机端口"),
    "attributes.net.peer.ip": _("对端 IP"),
    "attributes.net.peer.port": _("对端端口"),
    "attributes.net.peer.name": _("对端服务器名称"),
    "attributes.peer.service": _("对端服务名"),
    "attributes.trpc.callee_method": _("被调接口"),
    "attributes.trpc.callee_server": _("被调服务"),
    "attributes.trpc.callee_service": _("被调 Service"),
    "attributes.trpc.callee_ip": _("被调 IP"),
    "attributes.trpc.callee_container": _("被调容器"),
    "attributes.trpc.caller_method": _("主调接口"),
    "attributes.trpc.caller_server": _("主调服务"),
    "attributes.trpc.caller_service": _("主调 Service"),
    "attributes.trpc.caller_ip": _("主调 IP"),
    "attributes.trpc.caller_container": _("主调容器"),
    "attributes.trpc.envname": _("用户环境"),
    "attributes.trpc.namespace": _("物理环境"),
    "attributes.trpc.status_code": _("tRPC 状态码"),
    "attributes.trpc.status_msg": _("tRPC 状态详情"),
    "attributes.trpc.status_type": _("tRPC 状态类型"),
    "events.attributes.exception.escaped": "",
    "events.attributes.exception.message": _("异常详情"),
    "events.attributes.exception.stacktrace": _("异常堆栈"),
    "events.attributes.exception.type": _("异常类型"),
    "events.attributes.message": "",
    "events.name": _("事件名"),
    "events.timestamp": _("事件时间"),
    "resource.bk.instance.id": _("实例"),
    "resource.host.name": _("主机名称"),
    "resource.os.type": _("操作系统类型"),
    "resource.os.version": _("操作系统版本"),
    "resource.process.command": "",
    "resource.process.command_args": "",
    "resource.process.command_line": "",
    "resource.process.executable.name": "",
    "resource.process.executable.path": "",
    "resource.process.parent_pid": "",
    "resource.process.pid": "",
    "resource.process.runtime.description": "",
    "resource.process.runtime.name": "",
    "resource.process.runtime.version": "",
    "resource.service.name": _("服务名"),
    "resource.service.namespace": _("服务命名空间"),
    "resource.service.instance.id": _("服务实例"),
    "resource.service.version": _("服务版本"),
    "resource.k8s.bcs.cluster.id": _("BCS 集群 ID"),
    "resource.k8s.namespace.name": _("K8S 命名空间"),
    "resource.k8s.pod.ip": "K8S Pod IP",
    "resource.k8s.pod.name": _("K8S Pod 名"),
    "resource.net.host.port": _("主机端口"),
    "resource.net.host.name": _("主机名称"),
    "resource.net.host.ip": _("主机 IP"),
    "resource.host.ip": _("主机 IP"),
    "resource.telemetry.sdk.language": _("SDK 语言"),
    "resource.telemetry.sdk.name": _("SDK 名称"),
    "resource.telemetry.sdk.version": _("SDK 版本"),
    "status.code": _("状态"),
    "status.message": _("状态详情"),
}
