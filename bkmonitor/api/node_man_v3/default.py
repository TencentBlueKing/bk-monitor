"""NodeMan V3 原生协议；业务字段转换和版本选择由上层能力实现负责。"""

from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
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
        return settings.BKNODEMAN_V3_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL.rstrip('/')}/api/bk-nodemgr/prod/"

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


class ListV2CompatibleProcessesResource(NodeManV3Resource):
    """查询未迁移 V3 的 bkmonitorbeat 进程状态，返回内容兼容 V2 插件检索。"""

    action = "api/v3/process/list_v2_compatible"
    # 与 V2 plugin_search 一致，用 1min 缓存缓解短时间批量请求
    backend_cache_type = CacheType.SCENE_VIEW

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, label="业务ID列表")
        # 不传主机时接口会返回整个业务的主机，这里强制非空
        bk_host_id = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, label="主机ID列表")


class InstallPluginResource(NodeManV3Resource):
    """提交插件安装，返回 workflow_id。"""

    action = "api/v3/plugin/install"

    class RequestSerializer(serializers.Serializer):
        class PluginSerializer(serializers.Serializer):
            bk_host_id = serializers.IntegerField()
            plugin_name = serializers.CharField()
            version = serializers.CharField()

        plugin = PluginSerializer(many=True, allow_empty=False)


class CreateDeployPolicyResource(NodeManV3Resource):
    """创建部署策略，返回 deploy_policy_id。"""

    action = "api/v3/deploy_policy/create"

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField()
        description = serializers.CharField(allow_blank=True, default="")
        enabled = serializers.BooleanField(default=True)
        specs = serializers.ListField(child=serializers.DictField(), allow_empty=False)
        scopes = serializers.ListField(child=serializers.DictField(), allow_empty=True)


class UpdateDeployPolicyResource(NodeManV3Resource):
    """按 fields 指定的字段更新部署策略。"""

    action = "api/v3/deploy_policy/update"

    class RequestSerializer(serializers.Serializer):
        deploy_policies = serializers.ListField(child=serializers.DictField(), allow_empty=False)
        fields = serializers.DictField()


class ExecuteDeployPolicyResource(NodeManV3Resource):
    """执行部署策略，返回父 workflow_id；只表示已派发，不代表已收敛。"""

    action = "api/v3/deploy_policy/execute"

    class RequestSerializer(serializers.Serializer):
        deploy_policy_id = serializers.IntegerField()


class ListDeployPoliciesResource(NodeManV3Resource):
    """分页查询部署策略。"""

    action = "api/v3/deploy_policy/list"

    class RequestSerializer(serializers.Serializer):
        page = serializers.DictField()
        exact_include_conditions = serializers.DictField()
