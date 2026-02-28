"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any, cast

from bk_monitor_base.uptime_check import (
    TASK_MIN_PERIOD,
    UptimeCheckGroup,
    UptimeCheckTask,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
    get_group,
    get_task,
    list_groups,
    list_nodes,
    # 操作函数
    list_tasks,
    save_group,
    save_task,
)
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext as _

from bkmonitor.action.serializers import AuthorizeConfigSlz, BodyConfigSlz, KVPairSlz
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.ip import exploded_ip, is_v4, is_v6
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.views import serializers
from core.drf_resource.exceptions import CustomException

# 别名定义用于序列化器
UptimeCheckGroupDefine = UptimeCheckGroup
UptimeCheckTaskDefine = UptimeCheckTask


class AuthorizeConfigSerializer(AuthorizeConfigSlz):
    insecure_skip_verify = serializers.BooleanField(required=False, default=False)


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


class UptimeCheckTaskSerializer(serializers.Serializer):
    # 基本字段
    id = serializers.IntegerField(required=False)
    bk_tenant_id = serializers.CharField(required=False)
    bk_biz_id = serializers.IntegerField(required=True)
    name = serializers.CharField(max_length=128)
    protocol = serializers.ChoiceField(choices=["TCP", "UDP", "HTTP", "ICMP"])
    status = serializers.CharField(required=False)
    check_interval = serializers.IntegerField(required=False, default=5)
    location = serializers.JSONField(required=True)
    labels = serializers.JSONField(required=False, default=dict)

    # 独立数据源模式
    indepentent_dataid = serializers.BooleanField(required=False)

    # 关联字段
    config = ConfigSlz(required=True)

    # 读写属性
    create_user = serializers.CharField(required=False, allow_blank=True)
    create_time = serializers.DateTimeField(required=False)
    update_user = serializers.CharField(required=False, allow_blank=True)
    update_time = serializers.DateTimeField(required=False)

    # 只读字段
    url = serializers.ListField(required=False, child=serializers.CharField(), allow_empty=True)
    nodes = serializers.ListField(required=False, child=serializers.DictField(), allow_empty=True)
    groups = serializers.ListField(required=False, child=serializers.DictField(), allow_empty=True)
    available = serializers.FloatField(required=False, allow_null=True)
    task_duration = serializers.FloatField(required=False, allow_null=True)
    url_list = serializers.ListField(required=False, allow_null=True, allow_empty=True)

    is_deleted = serializers.BooleanField(default=False)

    def url_validate(self, url):
        try:
            URLValidator()(url)
            return True
        except ValidationError:
            return False

    def validate(self, attrs: dict[str, Any]):
        if attrs["config"]["period"] < TASK_MIN_PERIOD:
            raise CustomException(f"period must be greater than {TASK_MIN_PERIOD}s")
        has_targets = (
            attrs["config"].get("node_list") or attrs["config"].get("ip_list") or attrs["config"].get("url_list")
        )
        if attrs["protocol"] == UptimeCheckTaskProtocol.HTTP.value:
            if not attrs["config"].get("method") or not (
                attrs["config"].get("url_list") or attrs["config"].get("urls")
            ):
                raise CustomException("When protocol is HTTP, method and url_list is required in config.")
            if attrs["config"]["method"] in ["POST", "PUT", "PATCH"] and not attrs["config"].get("body"):
                raise CustomException("body is required in config.")
            for url in attrs["config"].get("url_list", []):
                if not self.url_validate(url):
                    raise CustomException("Not a valid URL")

        elif attrs["protocol"] == UptimeCheckTaskProtocol.ICMP.value:
            if not (attrs["config"].get("hosts") or has_targets):
                raise CustomException("When protocol is ICMP, targets is required in config.")
        else:
            if not attrs["config"].get("port") or not (attrs["config"].get("hosts") or has_targets):
                raise CustomException("When protocol is TCP/UDP, targets and port is required in config.")

        if attrs["protocol"] == UptimeCheckTaskProtocol.UDP.value:
            if "request" not in attrs["config"]:
                raise CustomException("request is required in config.")

        format_ips = []
        for ip in attrs["config"].get("ip_list", []):
            if is_v6(ip):
                format_ips.append(exploded_ip(ip))
            elif is_v4(ip):
                format_ips.append(ip)
            else:
                raise CustomException("Not a valid IP")
        return attrs

    def create(self, validated_data):
        """创建拨测任务（使用 operation 层）"""
        # 处理节点信息
        node_ids = validated_data.pop("node_id_list", [])
        group_ids = validated_data.pop("group_id_list", [])

        # 检查权限
        # 获取节点详情，区分公共节点和业务节点
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = validated_data["bk_biz_id"]
        # 获取操作人
        request = self.context.get("request")
        operator = request.user.username if request else ""

        node_objects = list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"node_ids": node_ids, "include_common": True},
        )
        common_nodes = [node for node in node_objects if node.is_common]

        # 如果存在公共节点，检查用户是否有权限使用
        if common_nodes and settings.ENABLE_PUBLIC_SYNTHETIC_LOCATION_AUTH:
            Permission().is_allowed(ActionEnum.USE_PUBLIC_SYNTHETIC_LOCATION, raise_exception=True)

        # 检查任务名称是否重复
        existing_tasks = list_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
        )
        # 精确匹配名称
        if any(task.name == validated_data["name"] for task in existing_tasks):
            raise CustomException(_("已存在相同名称的拨测任务"))

        # 独立数据源模式
        if settings.ENABLE_MULTI_TENANT_MODE:
            # 多租户模式下，必须使用独立数据源模式
            independent_dataid = True
        else:
            # 非多租户模式下，使用配置中的独立数据源模式
            if "independent_dataid" in validated_data:
                independent_dataid = validated_data["independent_dataid"]
            elif "indepentent_dataid" in validated_data:
                independent_dataid = validated_data["indepentent_dataid"]
            else:
                independent_dataid = False

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
            independent_dataid=independent_dataid,
        )

        task_id = save_task(task=task_define, operator=operator)
        return get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id).model_dump()

    def update(self, instance, validated_data):
        """更新拨测任务（使用 operation 层）"""
        node_ids = validated_data.pop("node_id_list", [])
        group_ids = validated_data.pop("group_id_list", [])

        # 获取租户、业务和操作人信息
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = validated_data["bk_biz_id"]
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 检查任务名称是否重复（排除自己）
        existing_tasks = list_tasks(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
        )

        if any(task.name == validated_data["name"] and task.id != instance.id for task in existing_tasks):
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

        task_id = save_task(task=task_define, operator=operator)
        return get_task(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_id=task_id).model_dump()


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

        tasks = list_tasks(
            bk_tenant_id=get_request_tenant_id(),
            bk_biz_id=obj.bk_biz_id,
            query={"task_ids": task_ids},
        )
        return tasks

    def validate(self, attrs: dict[str, Any]):
        if self.instance is None and "task_id_list" not in attrs:
            raise serializers.ValidationError(_("创建拨测任务组时需必传参数task_id_list"))
        return attrs

    def create(self, validated_data):
        """创建拨测分组（使用 operation 层）"""
        task_ids = validated_data.pop("task_id_list", [])
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = validated_data["bk_biz_id"]
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 检查分组名称是否重复
        existing_groups = list_groups(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
        )
        if any(group.name == validated_data["name"] for group in existing_groups):
            raise serializers.ValidationError(_("分组 %s 已存在！") % validated_data["name"])

        # 构建 UptimeCheckGroupDefine 进行创建
        group_define = UptimeCheckGroupDefine(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name=validated_data["name"],
            logo=validated_data.get("logo", ""),
            task_ids=task_ids,
        )

        group_id = save_group(group=group_define, operator=operator)
        return get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id)

    def update(self, instance, validated_data):
        """更新拨测分组（使用 operation 层）"""
        bk_tenant_id = cast(str, get_request_tenant_id())
        bk_biz_id = validated_data["bk_biz_id"]
        request = self.context.get("request")
        operator = request.user.username if request else ""

        # 检查分组名称是否重复（排除自己）
        existing_groups = list_groups(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            query={"name": validated_data["name"]},
        )
        instance_id = instance.id
        if any(group.id != instance_id and group.name == validated_data["name"] for group in existing_groups):
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

        group_id = save_group(group=group_define, operator=operator)
        return get_group(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, group_id=group_id)
