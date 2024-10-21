# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.utils import shortuuid
from bkmonitor.views import serializers
from core.drf_resource import resource
from core.drf_resource.base import Resource
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory


class GetTrapCollectorPluginResource(Resource):
    """
    用于获取SNMPTrap采集配置
    """

    class RequestSerializer(serializers.Serializer):
        class TrapConfigSlz(serializers.Serializer):
            class SnmpTrapSlz(serializers.Serializer):
                class AuthInfoSlz(serializers.Serializer):
                    security_name = serializers.CharField(required=False, label="安全名")
                    context_name = serializers.CharField(required=False, label="上下文名称", default="", allow_blank=True)
                    security_level = serializers.CharField(required=False, label="安全级别")
                    authentication_protocol = serializers.CharField(
                        required=False, label="验证协议", default="", allow_blank=True
                    )
                    authentication_passphrase = serializers.CharField(
                        required=False, label="验证口令", default="", allow_blank=True
                    )
                    privacy_protocol = serializers.CharField(required=False, label="隐私协议", default="", allow_blank=True)
                    privacy_passphrase = serializers.CharField(required=False, label="私钥", default="", allow_blank=True)
                    authoritative_engineID = serializers.CharField(required=False, label="设备ID")

                server_port = serializers.IntegerField(required=True, label="trap服务端口")
                listen_ip = serializers.CharField(required=True, label="trap监听地址")
                yaml = serializers.DictField(required=True, label="yaml配置文件")
                community = serializers.CharField(required=False, label="团体名", default="", allow_blank=True)
                aggregate = serializers.BooleanField(required=True, label="是否按周期聚合")
                version = serializers.ChoiceField(required=True, choices=["v1", "2c", "v2c", "v3"])
                auth_info = AuthInfoSlz(required=False, many=True, label="Trap V3认证信息", default=[])

            snmp_trap = SnmpTrapSlz(required=True, label="snmptrap配置信息")

        params = TrapConfigSlz(required=False, label="采集配置信息")
        plugin_id = serializers.CharField(required=True, label="插件ID")
        label = serializers.CharField(required=True, label="二级标签")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=False, label="采集配置ID")

    def perform_request(self, validated_request_data):
        plugin_id = validated_request_data["plugin_id"]
        label = validated_request_data["label"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        snmp_trap = validated_request_data["params"]["snmp_trap"]
        yaml = validated_request_data["params"]["snmp_trap"]["yaml"]
        if "id" not in validated_request_data:
            plugin_id = "trap_" + str(shortuuid.uuid())
            plugin_manager = PluginManagerFactory.get_manager(plugin=plugin_id, plugin_type=PluginType.SNMP_TRAP)
            params = plugin_manager.get_params(plugin_id, bk_biz_id, label, snmp_trap=snmp_trap, yaml=yaml)
            resource.plugin.create_plugin(params)
        else:
            plugin_manager = PluginManagerFactory.get_manager(plugin=plugin_id, plugin_type=PluginType.SNMP_TRAP)
            params = plugin_manager.get_params(plugin_id, bk_biz_id, label, snmp_trap=snmp_trap, yaml=yaml)
            plugin_manager.update_version(params)

        return plugin_id
