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

from bk_monitor_base.uptime_check import (
    TASK_MIN_PERIOD,
    UptimeCheckTaskProtocol,
)
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from bkmonitor.action.serializers import AuthorizeConfigSlz, BodyConfigSlz, KVPairSlz
from bkmonitor.utils.ip import exploded_ip, is_v4, is_v6
from bkmonitor.views import serializers
from core.drf_resource.exceptions import CustomException


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
