"""NodeMan V3 原生协议；业务字段转换和版本选择由上层能力实现负责。"""

from django.conf import settings
from rest_framework import serializers

from bk_monitor_base.config.nodeman import nodeman_v3_base_url
from bkmonitor.utils.user import get_admin_username
from core.drf_resource import APIResource
from core.errors.api import BKAPIError


class NodeManV3Resource(APIResource):
    """V3 code/data 协议，不继承 V2 API 或回退到 V2 地址。"""

    module_name = "node_man_v3"
    method = "POST"
    IS_STANDARD_FORMAT = False
    INSERT_BK_USERNAME_TO_REQUEST_DATA = False

    @property
    def base_url(self):
        return nodeman_v3_base_url(settings.BK_COMPONENT_API_URL)

    @property
    def label(self):
        return self.__doc__

    def full_request_data(self, validated_request_data):
        self.bk_username = get_admin_username(bk_tenant_id=self._get_tenant_id())
        return validated_request_data

    def render_response_data(self, validated_request_data, response_data):
        # V3 错误没有 result=False，不能依赖通用 V2 格式的错误判断。
        if response_data.get("code") != 0:
            raise BKAPIError(self.module_name, self.get_request_url(validated_request_data), response_data)
        return response_data["data"]


class ListHostsResource(NodeManV3Resource):
    """分页查询主机。"""

    action = "api/v3/topo/host/list"

    class RequestSerializer(serializers.Serializer):
        page = serializers.DictField()
        exact_include_conditions = serializers.DictField()


class DistinctHostsResource(NodeManV3Resource):
    """查询主机属性的去重值。"""

    action = "api/v3/topo/host/distinct"

    class RequestSerializer(serializers.Serializer):
        exact_include_conditions = serializers.DictField()


class ListBusinessesResource(NodeManV3Resource):
    """分页查询业务。"""

    action = "api/v3/topo/business/list"

    class RequestSerializer(serializers.Serializer):
        page = serializers.DictField()
        exact_include_conditions = serializers.DictField()


class ListNetworkAreasResource(NodeManV3Resource):
    """分页查询网络区域。"""

    action = "api/v3/topo/networkarea/list"

    class RequestSerializer(serializers.Serializer):
        page = serializers.DictField()
        exact_include_conditions = serializers.DictField()


class ListPluginsResource(NodeManV3Resource):
    """查询逻辑插件与包名映射。"""

    action = "api/v3/plugin/list"

    class RequestSerializer(serializers.Serializer):
        page = serializers.DictField()
        exact_include_conditions = serializers.DictField()


class ListPluginReleasesResource(NodeManV3Resource):
    """查询指定代际、平台的默认插件包。"""

    action = "api/v3/package/release/plugin/list"

    class RequestSerializer(serializers.Serializer):
        page = serializers.DictField()
        generation = serializers.IntegerField()
        exact_include_conditions = serializers.DictField()


class InstallPluginResource(NodeManV3Resource):
    """提交插件安装，返回 workflow_id。"""

    action = "api/v3/plugin/install"

    class RequestSerializer(serializers.Serializer):
        class PluginSerializer(serializers.Serializer):
            bk_host_id = serializers.IntegerField()
            plugin_name = serializers.CharField()
            version = serializers.CharField()

        plugin = PluginSerializer(many=True, allow_empty=False)
