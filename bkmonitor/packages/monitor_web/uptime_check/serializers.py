"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import arrow
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext as _

from bkmonitor.action.serializers import AuthorizeConfigSlz, BodyConfigSlz, KVPairSlz
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.ip import exploded_ip, is_v4, is_v6
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.views import serializers
from common.log import logger
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.drf_resource.exceptions import CustomException
from core.errors.uptime_check import UptimeCheckProcessError
from bk_monitor_base import uptime_check as uptime_check_operation
from bk_monitor_base.domains.uptime_check.constants import TASK_MIN_PERIOD
from bk_monitor_base.domains.uptime_check.define import (
    UptimeCheckGroup as UptimeCheckGroupDefine,
    UptimeCheckNode as UptimeCheckNodeDefine,
    UptimeCheckTask as UptimeCheckTaskDefine,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
    UptimeCheckNodeIPType,
)


class AuthorizeConfigSerializer(AuthorizeConfigSlz):
    insecure_skip_verify = serializers.BooleanField(required=False, default=False)


class UptimeCheckNodeSerializer(serializers.Serializer):
    """拨测节点序列化器（不依赖 Model，使用通用 Serializer）"""

    # 基本字段
    id = serializers.IntegerField(required=False, read_only=True)
    bk_tenant_id = serializers.CharField(required=False, read_only=True)
    bk_biz_id = serializers.IntegerField(required=True)
    name = serializers.CharField(max_length=50)
    is_common = serializers.BooleanField(required=False, default=False)
    biz_scope = serializers.ListField(required=False, default=list)
    ip_type = serializers.IntegerField(required=False, default=4)
    bk_host_id = serializers.IntegerField(required=False, allow_null=True)
    ip = serializers.CharField(required=False, allow_blank=True)
    plat_id = serializers.IntegerField(required=False, allow_null=True)
    location = serializers.JSONField(required=False, default=dict)
    carrieroperator = serializers.CharField(required=False, allow_blank=True, default="")

    # 读写属性
    create_user = serializers.CharField(required=False, read_only=True)
    create_time = serializers.DateTimeField(required=False, read_only=True)
    update_user = serializers.CharField(required=False, read_only=True)
    update_time = serializers.DateTimeField(required=False, read_only=True)

    def node_beat_check(self, validated_data) -> bool:
        """
        检查当前节点心跳
        """

        # TODO: 多租户环境下暂时跳过心跳检查
        if settings.ENABLE_MULTI_TENANT_MODE:
            return True

        if not is_ipv6_biz(validated_data["bk_biz_id"]):
            ip = validated_data.get("ip", "")
            bk_cloud_id = validated_data.get("plat_id", 0)
            if validated_data.get("bk_host_id"):
                host = api.cmdb.get_host_by_id(
                    bk_biz_id=validated_data["bk_biz_id"], bk_host_ids=[validated_data["bk_host_id"]]
                )
                if host:
                    ip = host[0].bk_host_innerip
                    bk_cloud_id = host[0].bk_cloud_id
            promql_statement = (
                f"bkmonitor:beat_monitor:heartbeat_total:uptime{{ip='{ip}',bk_cloud_id='{bk_cloud_id}'}}[3m]"
            )
        else:
            promql_statement = (
                f"bkmonitor:beat_monitor:heartbeat_total:uptime{{bk_host_id='{validated_data['bk_host_id']}'}}[3m]"
            )
        data_source_class = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)
        query_config = {
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "promql": promql_statement,
            "interval": 60,
            "alias": "a",
        }
        data_source = data_source_class(int(validated_data["bk_biz_id"]), **query_config)
        query = UnifyQuery(bk_biz_id=int(validated_data["bk_biz_id"]), data_sources=[data_source], expression="")
        end_time = arrow.utcnow().timestamp
        records = query.query_data(start_time=(end_time - 180) * 1000, end_time=end_time * 1000, limit=5)

        if len(records) > 0:
            return True

        raise UptimeCheckProcessError()

    def update(self, instance, validated_data):
        """
        更新节点
        """
        self.node_beat_check(validated_data)
        bk_tenant_id = get_request_tenant_id()
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 从 instance（定义对象）中获取原始值
        instance_id = instance.id
        instance_bk_biz_id = instance.bk_biz_id
        instance_is_common = instance.is_common

        if instance_is_common and not validated_data.get("is_common"):
            # 校验公共节点管理权限
            Permission().is_allowed(action=ActionEnum.MANAGE_PUBLIC_SYNTHETIC_LOCATION, raise_exception=True)

            # 检查是否有其他业务的任务在使用此公共节点
            tasks = uptime_check_operation.list_tasks(
                query={"node_ids": [instance_id]}, output={"format": "values", "fields": ["id", "name", "bk_biz_id"]}
            )
            other_biz_task = [
                _("{}(业务id:{})").format(task["name"], task["bk_biz_id"])
                for task in tasks
                if task["bk_biz_id"] != instance_bk_biz_id
            ]
            if other_biz_task:
                raise CustomException(
                    _("不能取消公共节点勾选，若要取消，请先删除以下任务的当前节点：%s") % "，".join(other_biz_task)
                )

        # 获取原始值
        original_biz_scope = instance.biz_scope
        original_location = instance.location
        original_carrieroperator = instance.carrieroperator
        original_ip_type = instance.ip_type
        original_bk_host_id = instance.bk_host_id
        original_ip = instance.ip
        original_plat_id = instance.plat_id

        # 构建 UptimeCheckNodeDefine 进行更新
        node_define = UptimeCheckNodeDefine(
            bk_tenant_id=bk_tenant_id,
            id=instance_id,
            bk_biz_id=validated_data.get("bk_biz_id", instance_bk_biz_id),
            name=validated_data.get("name", instance.name),
            is_common=validated_data.get("is_common", instance_is_common),
            biz_scope=validated_data.get("biz_scope", original_biz_scope),
            ip_type=UptimeCheckNodeIPType(validated_data.get("ip_type", original_ip_type)),
            bk_host_id=validated_data.get("bk_host_id", original_bk_host_id),
            ip=validated_data.get("ip", original_ip),
            plat_id=validated_data.get("plat_id", original_plat_id),
            location=validated_data.get("location", original_location),
            carrieroperator=validated_data.get("carrieroperator", original_carrieroperator),
        )
        node_id = uptime_check_operation.save_node(node=node_define, operator=operator)

        # 返回更新后的节点定义对象
        return uptime_check_operation.get_node(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_data.get("bk_biz_id", instance_bk_biz_id),
            node_id=node_id,
            output={"format": "define"},
        )

    def create(self, validated_data):
        """
        创建节点
        """
        if validated_data.get("is_common"):
            # 校验公共节点管理权限
            Permission().is_allowed(action=ActionEnum.MANAGE_PUBLIC_SYNTHETIC_LOCATION, raise_exception=True)
        self.node_beat_check(validated_data)

        bk_tenant_id = get_request_tenant_id()
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 构建 UptimeCheckNodeDefine 进行创建
        node_define = UptimeCheckNodeDefine(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_data["bk_biz_id"],
            name=validated_data["name"],
            is_common=validated_data.get("is_common", False),
            biz_scope=validated_data.get("biz_scope", []),
            ip_type=UptimeCheckNodeIPType(validated_data.get("ip_type", 4)),
            bk_host_id=validated_data.get("bk_host_id"),
            ip=validated_data.get("ip"),
            plat_id=validated_data.get("plat_id"),
            location=validated_data.get("location", {}),
            carrieroperator=validated_data.get("carrieroperator", ""),
        )
        node_id = uptime_check_operation.save_node(node=node_define, operator=operator)
        return uptime_check_operation.get_node(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_data["bk_biz_id"],
            node_id=node_id,
            output={"format": "define"},
        )


class ConfigSlz(serializers.Serializer):
    class HostSlz(serializers.Serializer):
        bk_host_id = serializers.IntegerField(required=False, allow_null=True)
        ip = serializers.CharField(required=False, allow_blank=True)
        # outer_ip设为required=False,兼容此前通过文件导入的任务hosts没有传outer_ip
        outer_ip = serializers.CharField(required=False, allow_blank=True)
        target_type = serializers.CharField(required=False, allow_blank=True)

        # 动态节点
        bk_biz_id = serializers.IntegerField(required=False)
        bk_inst_id = serializers.IntegerField(required=False)
        bk_obj_id = serializers.CharField(required=False, allow_blank=True)
        node_path = serializers.CharField(required=False, allow_blank=True)

    # HTTP ONLY
    method = serializers.ChoiceField(
        required=False,
        default="GET",
        choices=[("GET", "GET"), ("POST", "POST"), ("PUT", "PUT"), ("PATCH", "PATCH"), ("DELETE", "DELETE")],
    )
    authorize = AuthorizeConfigSerializer(required=False)
    body = BodyConfigSlz(required=False)
    query_params = serializers.ListField(required=False, child=KVPairSlz(), default=[])
    headers = serializers.ListField(required=False, default=[])
    response_code = serializers.CharField(required=False, default="", allow_blank=True)

    # TCP&UDP
    port = serializers.CharField(required=False)

    # TCP&UDP&ICMP
    node_list = HostSlz(required=False, many=True)
    ip_list = serializers.ListField(required=False, default=[])
    output_fields = serializers.ListField(required=False, default=settings.UPTIMECHECK_OUTPUT_FIELDS)
    target_ip_type = serializers.ChoiceField(required=False, default=0, choices=[0, 4, 6])
    dns_check_mode = serializers.ChoiceField(required=False, default="single", choices=["all", "single"])

    # UDP
    request = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    request_format = serializers.CharField(required=False)
    wait_empty_response = serializers.BooleanField(required=False)

    # ICMP ONLY
    max_rtt = serializers.IntegerField(required=False)
    total_num = serializers.IntegerField(required=False)
    size = serializers.IntegerField(required=False)
    send_interval = serializers.CharField(required=False)
    target_labels = serializers.DictField(required=False)

    # COMMON
    url_list = serializers.ListField(required=False, default=[])
    period = serializers.IntegerField(required=True)
    response_format = serializers.CharField(required=False)
    response = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    # 这里timeout 对应 采集器配置项: available_duration
    timeout = serializers.IntegerField(required=False, max_value=settings.MAX_AVAILABLE_DURATION_LIMIT)

    # ORIGIN CONFIG
    urls = serializers.URLField(required=False)
    hosts = HostSlz(required=False, many=True)


class UptimeCheckTaskBaseSerializer(serializers.Serializer):
    def url_validate(self, url):
        try:
            URLValidator()(url)
            return True
        except ValidationError:
            return False

    def validate(self, data):
        if data["config"]["period"] < TASK_MIN_PERIOD:
            raise CustomException("period must be greater than 10")
        has_targets = data["config"].get("node_list") or data["config"].get("ip_list") or data["config"].get("url_list")
        if data["protocol"] == UptimeCheckTaskProtocol.HTTP.value:
            if not data["config"].get("method") or not (data["config"].get("url_list") or data["config"].get("urls")):
                raise CustomException("When protocol is HTTP, method and url_list is required in config.")
            if data["config"]["method"] in ["POST", "PUT", "PATCH"] and not data["config"].get("body"):
                raise CustomException("body is required in config.")
            for url in data["config"].get("url_list", []):
                if not self.url_validate(url):
                    raise CustomException("Not a valid URL")

        elif data["protocol"] == UptimeCheckTaskProtocol.ICMP.value:
            if not (data["config"].get("hosts") or has_targets):
                raise CustomException("When protocol is ICMP, targets is required in config.")
        else:
            if not data["config"].get("port") or not (data["config"].get("hosts") or has_targets):
                raise CustomException("When protocol is TCP/UDP, targets and port is required in config.")

        if data["protocol"] == UptimeCheckTaskProtocol.UDP.value:
            if "request" not in data["config"]:
                raise CustomException("request is required in config.")

        format_ips = []
        for ip in data["config"].get("ip_list", []):
            if is_v6(ip):
                format_ips.append(exploded_ip(ip))
            elif is_v4(ip):
                format_ips.append(ip)
            else:
                raise CustomException("Not a valid IP")
        return data


class UptimeCheckTaskSerializer(UptimeCheckTaskBaseSerializer):
    """拨测任务序列化器（不依赖 Model，使用通用 Serializer 的部分字段）"""

    # 基本字段
    id = serializers.IntegerField(required=False, read_only=True)
    bk_tenant_id = serializers.CharField(required=False, read_only=True)
    bk_biz_id = serializers.IntegerField(required=True)
    name = serializers.CharField(max_length=128)
    protocol = serializers.ChoiceField(choices=["TCP", "UDP", "HTTP", "ICMP"])
    status = serializers.CharField(required=False, read_only=True)
    check_interval = serializers.IntegerField(required=False, default=5)
    location = serializers.JSONField(required=True)
    labels = serializers.JSONField(required=False, default=dict)

    # 关联字段
    config = ConfigSlz(required=True)
    node_id_list = serializers.ListField(required=True, write_only=True)
    group_id_list = serializers.ListField(required=False, write_only=True)

    # 读写属性
    create_user = serializers.CharField(required=False, read_only=True)
    create_time = serializers.DateTimeField(required=False, read_only=True)
    update_user = serializers.CharField(required=False, read_only=True)
    update_time = serializers.DateTimeField(required=False, read_only=True)

    # 只读字段
    nodes = serializers.SerializerMethodField(read_only=True)
    groups = serializers.SerializerMethodField(read_only=True)
    available = serializers.SerializerMethodField(read_only=True)
    task_duration = serializers.SerializerMethodField(read_only=True)
    url_list = serializers.SerializerMethodField(read_only=True)

    @staticmethod
    def get_url_list(obj):
        """拼接拨测地址"""
        protocol = (
            obj.protocol
            if isinstance(obj.protocol, str)
            else obj.protocol.value
            if hasattr(obj.protocol, "value")
            else str(obj.protocol)
        )
        config = obj.config
        bk_biz_id = obj.bk_biz_id

        if protocol == UptimeCheckTaskProtocol.HTTP.value:
            # 针对HTTP协议
            if config.get("urls"):
                url_list = [config["urls"]]
            else:
                url_list = config.get("url_list", [])
            return url_list

        if not config.get("hosts", []):
            if config.get("node_list"):
                params = {
                    "hosts": config["node_list"],
                    "output_fields": config.get("output_fields", settings.UPTIMECHECK_OUTPUT_FIELDS),
                    "bk_biz_id": bk_biz_id,
                }
                node_instance = resource.uptime_check.topo_template_host(**params)
            else:
                node_instance = []

            host_instance = config.get("url_list", []) + config.get("ip_list", [])
            if node_instance:
                target_host = node_instance + host_instance
            else:
                target_host = host_instance
        else:
            # 兼容旧版hosts逻辑
            # 针对其他协议
            if len(config["hosts"]) and config["hosts"][0].get("bk_obj_id"):
                # 如果是动态拓扑，拿到所有的IP
                params = {
                    "hosts": config["hosts"],
                    "output_fields": ["bk_host_innerip"],
                    "bk_biz_id": bk_biz_id,
                }
                target_host = resource.uptime_check.topo_template_host(**params)
            else:
                target_host = [host["ip"] for host in config["hosts"] if host.get("ip")]

        # 拼接拨测地址
        if protocol == UptimeCheckTaskProtocol.ICMP.value:
            return target_host
        else:
            return ["[{}]:{}".format(host, config["port"]) for host in target_host]

    def get_nodes(self, obj):
        """获取任务节点列表"""
        node_ids = [n.pk for n in (obj.nodes.all() if hasattr(obj, "nodes") else [])]

        if not node_ids:
            return []

        nodes = uptime_check_operation.list_nodes(
            bk_tenant_id=get_request_tenant_id(), query={"node_ids": node_ids}, output={"format": "define"}
        )
        return UptimeCheckNodeSerializer(nodes, many=True).data

    def get_groups(self, obj):
        """获取任务分组信息"""
        task_id = obj.id

        groups = uptime_check_operation.list_groups(
            bk_tenant_id=get_request_tenant_id(),
            bk_biz_id=obj.bk_biz_id,
            query={"task_id": task_id},
            output={"format": "values", "fields": ["id", "name"]},
        )
        return groups

    def get_available(self, obj):
        """计算任务可用率，如异常则按0计算，不可影响任务列表的获取"""
        # 只有拨测任务列表列需要展示每个拨测任务的可用率情况
        # 需要展示每个任务可用率时，则调用 list() 方法时指定 get_available=True
        task_id = obj.id
        status = (
            obj.status
            if isinstance(obj.status, str)
            else obj.status.value
            if hasattr(obj.status, "value")
            else str(obj.status)
        )

        if (
            self.context.get("request").query_params.get("get_available", False)
            and status != UptimeCheckTaskStatus.STOPED.value
        ):
            try:
                task_data = resource.uptime_check.get_recent_task_data({"task_id": task_id, "type": "available"})
                return task_data["available"] * 100
            except Exception as e:
                logger.exception(f"get available failed: {str(e)}")
                return 0
        else:
            return None

    def get_task_duration(self, obj):
        """计算任务响应时长"""
        task_id = obj.id
        status = (
            obj.status
            if isinstance(obj.status, str)
            else obj.status.value
            if hasattr(obj.status, "value")
            else str(obj.status)
        )

        if (
            self.context.get("request").query_params.get("get_task_duration", False)
            and status != UptimeCheckTaskStatus.STOPED.value
        ):
            try:
                task_data = resource.uptime_check.get_recent_task_data({"task_id": task_id, "type": "task_duration"})
                return task_data["task_duration"]
            except Exception as e:
                logger.exception(f"get task duration failed:{str(e)}")
                return None
        else:
            return None

    def create(self, validated_data):
        """创建拨测任务（使用 operation 层）"""
        # 处理节点信息
        node_ids = validated_data.pop("node_id_list", [])
        group_ids = validated_data.pop("group_id_list", [])

        # 检查权限
        # 获取节点详情，区分公共节点和业务节点
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = validated_data["bk_biz_id"]
        # 获取操作人
        request = self.context.get("request")
        operator = request.user.username if request else ""

        node_objects = uptime_check_operation.list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"node_ids": node_ids, "include_common": True},
            output={"format": "define"},
        )
        common_nodes = [node for node in node_objects if node.is_common]

        # 如果存在公共节点，检查用户是否有权限使用
        if common_nodes and settings.ENABLE_PUBLIC_SYNTHETIC_LOCATION_AUTH:
            Permission().is_allowed(ActionEnum.USE_PUBLIC_SYNTHETIC_LOCATION, raise_exception=True)

        # 检查任务名称是否重复
        existing_tasks = uptime_check_operation.list_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
            output={"format": "values", "fields": ["id", "name"]},
        )
        # 精确匹配名称
        if any(task["name"] == validated_data["name"] for task in existing_tasks):
            raise CustomException(_("已存在相同名称的拨测任务"))

        # 构建 UptimeCheckTaskDefine 进行创建
        task_define = UptimeCheckTaskDefine(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name=validated_data["name"],
            protocol=UptimeCheckTaskProtocol(validated_data["protocol"]),
            config=validated_data["config"],
            labels=validated_data.get("labels", {}),
            check_interval=validated_data["config"].get("period", 5),
            location=validated_data.get("location", {}),
            node_ids=node_ids,
            group_ids=group_ids,
            # 多租户模式下，独立数据源模式
            independent_dataid=settings.ENABLE_MULTI_TENANT_MODE,
        )

        task_id = uptime_check_operation.save_task(task=task_define, operator=operator)
        return uptime_check_operation.get_task(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id, output={"format": "define"}
        )

    def update(self, instance, validated_data):
        """更新拨测任务（使用 operation 层）"""
        node_ids = validated_data.pop("node_id_list", [])
        group_ids = validated_data.pop("group_id_list", [])

        # 获取租户、业务和操作人信息
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = validated_data["bk_biz_id"]
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 检查任务名称是否重复（排除自己）
        existing_tasks = uptime_check_operation.list_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
            output={"format": "values", "fields": ["id", "name"]},
        )
        # 精确匹配名称，排除自己
        if any(task["name"] == validated_data["name"] and task["id"] != instance.id for task in existing_tasks):
            raise CustomException(_("已存在相同名称的拨测任务"))

        # 构建 UptimeCheckTaskDefine 进行更新
        task_define = UptimeCheckTaskDefine(
            bk_tenant_id=bk_tenant_id,
            id=instance.id,
            bk_biz_id=bk_biz_id,
            name=validated_data["name"],
            protocol=UptimeCheckTaskProtocol(validated_data["protocol"]),
            config=validated_data["config"],
            labels=validated_data.get("labels", instance.labels or {}),
            check_interval=validated_data["config"].get("period", instance.check_interval),
            location=validated_data.get("location", instance.location or {}),
            node_ids=node_ids,
            group_ids=group_ids,
            status=UptimeCheckTaskStatus(instance.status),
            independent_dataid=instance.indepentent_dataid,
        )

        task_id = uptime_check_operation.save_task(task=task_define, operator=operator)
        return uptime_check_operation.get_task(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id, output={"format": "define"}
        )


class UptimeCheckGroupSerializer(serializers.Serializer):
    """拨测分组序列化器（不依赖 Model，使用通用 Serializer）"""

    # 基本字段
    id = serializers.IntegerField(required=False, read_only=True)
    bk_tenant_id = serializers.CharField(required=False, read_only=True)
    bk_biz_id = serializers.IntegerField(required=True)
    name = serializers.CharField(max_length=50)
    logo = serializers.CharField(required=False, default="")

    # 关联字段
    task_id_list = serializers.ListField(required=False, write_only=True)

    # 读写属性
    create_user = serializers.CharField(required=False, read_only=True)
    create_time = serializers.DateTimeField(required=False, read_only=True)
    update_user = serializers.CharField(required=False, read_only=True)
    update_time = serializers.DateTimeField(required=False, read_only=True)

    # 只读字段
    tasks = serializers.SerializerMethodField(read_only=True)

    def get_tasks(self, obj):
        """获取分组任务列表"""
        task_ids = [t.pk for t in (obj.tasks.filter(is_deleted=False) if hasattr(obj, "tasks") else [])]

        if not task_ids:
            return []

        tasks = uptime_check_operation.list_tasks(
            bk_tenant_id=get_request_tenant_id(),
            bk_biz_id=obj.bk_biz_id,
            query={"task_ids": task_ids},
            output={"format": "dict"},
        )
        return tasks

    def validate(self, data):
        if self.instance is None and "task_id_list" not in data:
            raise serializers.ValidationError(_("创建拨测任务组时需必传参数task_id_list"))
        return data

    def create(self, validated_data):
        """创建拨测分组（使用 operation 层）"""
        task_ids = validated_data.pop("task_id_list", [])
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = validated_data["bk_biz_id"]
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 使用新版 list_groups API 检查分组名称是否重复
        existing_groups = uptime_check_operation.list_groups(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
            output={"format": "values", "fields": ["id", "name"]},
        )
        if any(group["name"] == validated_data["name"] for group in existing_groups):
            raise serializers.ValidationError(_("分组 %s 已存在！") % validated_data["name"])

        # 构建 UptimeCheckGroupDefine 进行创建
        group_define = UptimeCheckGroupDefine(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name=validated_data["name"],
            logo=validated_data.get("logo", ""),
            task_ids=task_ids,
        )

        group_id = uptime_check_operation.save_group(group=group_define, operator=operator)
        return uptime_check_operation.get_group(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id, output={"format": "define"}
        )

    def update(self, instance, validated_data):
        """更新拨测分组（使用 operation 层）"""
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = validated_data["bk_biz_id"]
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 检查分组名称是否重复（排除自己）
        existing_groups = uptime_check_operation.list_groups(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
            output={"format": "values", "fields": ["id", "name"]},
        )
        instance_id = instance.id
        if any(group["id"] != instance_id and group["name"] == validated_data["name"] for group in existing_groups):
            raise serializers.ValidationError(_("分组 %s 已存在！") % validated_data["name"])

        task_ids = validated_data.pop("task_id_list", None)

        # 获取原始任务ID列表
        original_task_ids = [task.id for task in instance.tasks.all()]

        # 构建 UptimeCheckGroupDefine 进行更新
        group_define = UptimeCheckGroupDefine(
            bk_tenant_id=bk_tenant_id,
            id=instance_id,
            bk_biz_id=bk_biz_id,
            name=validated_data["name"],
            logo=validated_data.get("logo", instance.logo),
            task_ids=task_ids if task_ids is not None else original_task_ids,
        )

        group_id = uptime_check_operation.save_group(group=group_define, operator=operator)
        # 使用新版 get_group API 替代 get_uptime_check_group
        return uptime_check_operation.get_group(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id, output={"format": "define"}
        )
