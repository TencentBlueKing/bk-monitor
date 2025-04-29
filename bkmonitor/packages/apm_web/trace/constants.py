"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from enum import Enum

from django.utils.translation import gettext_lazy as _


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

    EQ = {"operator": "equal", "label": "=", "placeholder": _("请选择或直接输入，Enter分隔")}
    EQ_WILDCARD = {
        "operator": "equal",
        "label": "=",
        "placeholder": _("请选择或直接输入，Enter分隔"),
        "wildcard_operator": "like",
    }
    NE = {"operator": "not_equal", "label": "!=", "placeholder": _("请选择或直接输入，Enter分隔")}
    NE_WILDCARD = {
        "operator": "not_equal",
        "label": "!=",
        "placeholder": _("请选择或直接输入，Enter分隔"),
        "wildcard_operator": "like",
    }

    EXISTS = {"operator": "exists", "label": _("存在"), "placeholder": _("确认字段已存在")}
    NOT_EXISTS = {"operator": "not exists", "label": _("不存在"), "placeholder": _("确认字段不存在")}
    INCLUDE = {"operator": "like", "label": _("包含"), "placeholder": _("请选择或直接输入，Enter分隔")}


OPERATORS = {
    "keyword": [
        OperatorEnum.EQ_WILDCARD,
        OperatorEnum.NE_WILDCARD,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
        OperatorEnum.INCLUDE,
    ],
    "text": [
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "integer": [
        OperatorEnum.EQ_WILDCARD,
        OperatorEnum.NE_WILDCARD,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "long": [
        OperatorEnum.EQ_WILDCARD,
        OperatorEnum.NE_WILDCARD,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "double": [
        OperatorEnum.EQ_WILDCARD,
        OperatorEnum.NE_WILDCARD,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "date": [
        OperatorEnum.EQ,
        OperatorEnum.NE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
    "boolean": [OperatorEnum.EXISTS, OperatorEnum.NOT_EXISTS],
    "conflict": [
        OperatorEnum.EQ,
        OperatorEnum.NE,
        OperatorEnum.EXISTS,
        OperatorEnum.NOT_EXISTS,
    ],
}

TRACE_FIELD_ALIAS = {
    "hierarchy_count": _("Span 层数"),
    "service_count": _("服务数量"),
    "span_count": _("Span 数量"),
    "root_service": _("入口服务"),
    "root_service_span_id": _("入口服务根 Span"),
    "root_service_span_name": _("入口接口"),
    "root_service_status_code": _("状态码"),
    "root_service_category": _("调用类型"),
    "root_service_kind": _("入口服务类型"),
    "root_span_id": _("根 Span ID"),
    "root_span_name": _("根 Span"),
    "root_span_service": _("根 Span 服务"),
    "root_span_kind": _("根 Span 类型"),
    "error": _("错误详情"),
    "error_count": _("错误数"),
    "min_start_time": _("开始时间"),
    "max_end_time": _("结束时间"),
    "trace_duration": _("耗时"),
    "elapsed_time": _("耗时"),
    "end_time": _("结束时间"),
    "kind": _("类型"),
    "links": _("关联链接"),
    "parent_span_id": _("父 Span ID"),
    "span_id": "Span ID",
    "span_name": _("接口名称"),
    "start_time": _("开始时间"),
    "time": _("时间"),
    "trace_id": "Trace ID",
    "trace_state": _("Trace 状态"),
    "category_statistics.async_backend": _("Async 数量"),
    "category_statistics.db": _("DB 数量"),
    "category_statistics.http": _("HTTP 数量"),
    "category_statistics.messaging": _("Messaging 数量"),
    "category_statistics.other": _("Other 数量"),
    "category_statistics.rpc": _("RPC 数量"),
    "kind_statistics.async": _("异步 Span 数量"),
    "kind_statistics.interval": _("内部 Span 数量"),
    "kind_statistics.sync": _("同步 Span 数量"),
    "kind_statistics.unspecified": _("未知 Span 数量"),
    "attributes.apdex_type": "",
    "attributes.http.host": "HTTP Host",
    "attributes.http.url": "HTTP URL",
    "attributes.server.address": _("服务地址"),
    "attributes.http.scheme": _("HTTP协议"),
    "attributes.http.flavor": _("HTTP服务名称"),
    "attributes.http.route": "",
    "attributes.http.server_name": "",
    "attributes.http.target": "",
    "attributes.http.method": _("HTTP方法"),
    "attributes.http.status_code": _("HTTP状态码"),
    "attributes.rpc.method": _("RPC方法"),
    "attributes.rpc.service": _("RPC服务"),
    "attributes.rpc.system": _("RPC系统名"),
    "attributes.rpc.grpc.status_code": _("gRPC状态码"),
    "attributes.db.name": _("数据库名称"),
    "attributes.db.operation": _("数据库操作"),
    "attributes.db.system": _("数据库类型"),
    "attributes.db.statement": _("数据库语句"),
    "attributes.db.instance": _("数据库实例ID"),
    "attributes.messaging.system": _("消息系统"),
    "attributes.messaging.destination": _("消息目的地"),
    "attributes.messaging.destination_kind": _("消息目的地类型"),
    "attributes.celery.action": _("操作名称"),
    "attributes.celery.task_name": _("任务名称"),
    "attributes.http.user_agent": "",
    "attributes.net.host.name": "",
    "attributes.net.host.port": "",
    "attributes.net.peer.ip": "",
    "attributes.net.peer.port": "",
    "attributes.net.peer.name": _("远程服务器名称"),
    "attributes.peer.service": _("远程服务名"),
    "events.attributes.exception.escaped": "",
    "events.attributes.exception.message": "",
    "events.attributes.exception.stacktrace": "",
    "events.attributes.exception.type": "",
    "events.attributes.message": "",
    "events.name": "",
    "events.timestamp": "",
    "resource.bk.instance.id": _("实例"),
    "resource.host.name": "",
    "resource.os.type": "",
    "resource.os.version": "",
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
    "resource.service.instance.id": _("服务实例ID"),
    "resource.service.version": _("服务版本"),
    "resource.k8s.bcs.cluster.id": _("K8S BCS 集群 ID"),
    "resource.k8s.namespace.name": _("K8S 命名空间"),
    "resource.k8s.pod.ip": "K8S Pod Ip",
    "resource.k8s.pod.name": _("K8S Pod 名称"),
    "resource.net.host.port": _("主机端口"),
    "resource.net.host.name": _("主机名称"),
    "resource.net.host.ip": _("主机IP"),
    "resource.host.ip": _("主机IP"),
    "resource.telemetry.sdk.language": _("SDK语言"),
    "resource.telemetry.sdk.name": _("SDK名称"),
    "resource.telemetry.sdk.version": _("SDK版本"),
    "status.code": _("状态"),
    "status.message": "",
}
