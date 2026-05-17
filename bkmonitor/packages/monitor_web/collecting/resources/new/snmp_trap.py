"""SNMP Trap 采集配置 Resource —— 适配 bk-monitor-base 的新实现。

[ISSUE] 虚拟插件创建仍依赖旧版 PluginManagerFactory 和 resource.plugin.create_plugin。
如果 plugin 模块已切换到 base 模式（ENABLE_BK_MONITOR_BASE_PLUGIN=true），
则 resource.plugin.create_plugin 走的是 base 的 create_metric_plugin，逻辑上兼容。
如果 plugin 模块未切换，则走旧 ORM 路径。
两种情况下本 Resource 的接口行为一致。
"""

from __future__ import annotations

from bkmonitor.utils import shortuuid
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.views import serializers
from core.drf_resource import resource
from core.drf_resource.base import Resource
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory


class GetTrapCollectorPluginResource(Resource):
    """用于获取 SNMPTrap 采集配置对应的虚拟插件。

    仅被 SaveCollectConfigResource 内部调用。
    """

    class RequestSerializer(serializers.Serializer):
        class TrapConfigSlz(serializers.Serializer):
            class SnmpTrapSlz(serializers.Serializer):
                class AuthInfoSlz(serializers.Serializer):
                    security_name = serializers.CharField(required=False, label="安全名")
                    context_name = serializers.CharField(
                        required=False, label="上下文名称", default="", allow_blank=True
                    )
                    security_level = serializers.CharField(required=False, label="安全级别")
                    authentication_protocol = serializers.CharField(
                        required=False, label="验证协议", default="", allow_blank=True
                    )
                    authentication_passphrase = serializers.CharField(
                        required=False, label="验证口令", default="", allow_blank=True
                    )
                    privacy_protocol = serializers.CharField(
                        required=False, label="隐私协议", default="", allow_blank=True
                    )
                    privacy_passphrase = serializers.CharField(
                        required=False, label="私钥", default="", allow_blank=True
                    )
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

    def perform_request(self, validated_request_data: dict) -> str:
        bk_tenant_id = get_request_tenant_id()
        plugin_id = validated_request_data["plugin_id"]
        label = validated_request_data["label"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        snmp_trap = validated_request_data["params"]["snmp_trap"]
        yaml = validated_request_data["params"]["snmp_trap"]["yaml"]

        if "id" not in validated_request_data:
            plugin_id = "trap_" + str(shortuuid.uuid())
            plugin_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.SNMP_TRAP
            )
            params = plugin_manager.get_params(plugin_id, bk_biz_id, label, snmp_trap=snmp_trap, yaml=yaml)
            resource.plugin.create_plugin(params)
        else:
            plugin_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.SNMP_TRAP
            )
            params = plugin_manager.get_params(plugin_id, bk_biz_id, label, snmp_trap=snmp_trap, yaml=yaml)
            plugin_manager.update_version(params)

        return plugin_id
