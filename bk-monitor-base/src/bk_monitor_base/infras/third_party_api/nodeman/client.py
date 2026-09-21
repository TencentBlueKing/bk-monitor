from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient, BkApiMode


class NodeManApiClient(BkApiClient, ABC):
    """
    节点管理 API Client
    """

    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "nodeman"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/nodeman/"
    apigw_base_url: ClassVar[str] = "api/bk-nodeman/prod/"

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


class NodeManControlApiClient(NodeManApiClient, ABC):
    """可单独路由的兼容控制面，不影响 V2 Subscription 和采集插件实例。

    使用既有 blueking.api_configs 的 nodeman_control 配置；未配置时保持原部署。
    配置存在时必须提供入口，不能因配置错误或请求失败隐式回到 V2。
    """

    @override
    def _get_api_mode(self) -> BkApiMode:
        """兼容控制面默认使用 APIGW，多租户始终使用 APIGW。"""
        control_config = self.config.blueking.api_configs.get("nodeman_control")
        if control_config is None:
            return super()._get_api_mode()
        if self.config.blueking.enable_multi_tenancy:
            return BkApiMode.APIGW
        return BkApiMode(control_config.mode or "apigw")

    @override
    def _get_api_url(self, params: dict[str, Any]) -> str:
        """按当前控制面配置构建 URL，保留原接口参数和返回值。"""
        control_config = self.config.blueking.api_configs.get("nodeman_control")
        if control_config is None:
            return super()._get_api_url(params)
        if not control_config.custom_api_url:
            raise ValueError("nodeman_control.custom_api_url must be configured")
        if self._get_api_mode() == BkApiMode.APIGW:
            path, path_keys = self.apigw_path, self.apigw_path_keys
            # 与监控主仓一致：Host/Plugin 兼容接口仅在多租户下使用 system 路径。
            if not self.config.blueking.enable_multi_tenancy and path.startswith("system/api/"):
                path = path.removeprefix("system/")
        else:
            path, path_keys = self.esb_path, self.esb_path_keys
        url = f"{str(control_config.custom_api_url).rstrip('/')}/{path.lstrip('/')}"
        return self._format_path(url, path_keys, params)


class UploadPlugin(NodeManApiClient):
    """
    上传 API Client
    """

    action: ClassVar[str] = "upload_plugin"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "backend/api/plugin/upload/"
    apigw_path: ClassVar[str] = "backend/api/plugin/upload/"


class CreateRegisterPluginTask(NodeManApiClient):
    """
    注册插件 API Client
    """

    action: ClassVar[str] = "create_register_plugin_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_create_register_task/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/create_register_task/"


class QueryRegisterPluginTask(NodeManApiClient):
    """
    查询注册插件任务 API Client
    """

    action: ClassVar[str] = "query_register_plugin_task"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "plugin_query_register_task/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/query_register_task/"


class GetPluginInfo(NodeManApiClient):
    """
    获取插件信息 API Client
    """

    action: ClassVar[str] = "get_plugin_info"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "plugin_info/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/info/"


class ReleasePlugin(NodeManApiClient):
    """
    发布插件 API Client
    """

    action: ClassVar[str] = "release_plugin"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_release/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/release/"


class CreatePluginConfigTemplate(NodeManApiClient):
    """
    创建插件配置模板 API Client
    """

    action: ClassVar[str] = "create_plugin_config_template"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_create_config_template/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/create_config_template/"


class ReleasePluginConfigTemplate(NodeManApiClient):
    """
    发布插件配置模板 API Client
    """

    action: ClassVar[str] = "release_plugin_config_template"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_release_config_template/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/release_config_template/"


class CreateExportPluginTask(NodeManApiClient):
    """
    创建导出插件任务 API Client
    """

    action: ClassVar[str] = "create_export_plugin_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_create_export_task/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/create_export_task/"


class QueryExportPluginTask(NodeManApiClient):
    """
    查询导出插件任务 API Client
    """

    action: ClassVar[str] = "query_export_plugin_task"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "plugin_query_export_task/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/query_export_task/"


class RenderPluginConfigTemplate(NodeManApiClient):
    """
    渲染插件配置模板 API Client
    """

    action: ClassVar[str] = "render_plugin_config_template"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_render_config_template/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/render_config_template/"


class StartPluginDebug(NodeManApiClient):
    """
    启动插件调试 API Client
    """

    action: ClassVar[str] = "start_plugin_debug"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_start_debug/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/start_debug/"


class QueryPluginDebug(NodeManApiClient):
    """
    查询插件调试 API Client
    """

    action: ClassVar[str] = "query_plugin_debug"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "plugin_query_debug/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/query_debug/"


class StopPluginDebug(NodeManApiClient):
    """
    停止插件调试 API Client
    """

    action: ClassVar[str] = "stop_plugin_debug"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "plugin_stop_debug/"
    apigw_path: ClassVar[str] = "system/backend/api/plugin/stop_debug/"


class SwitchSubscription(NodeManApiClient):
    """
    启停订阅 API Client
    """

    action: ClassVar[str] = "switch_subscription"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "subscription_switch/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/switch/"


class RunSubscription(NodeManApiClient):
    """
    运行订阅 API Client
    """

    action: ClassVar[str] = "run_subscription"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "subscription_run/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/run/"


class CreateSubscription(NodeManApiClient):
    """
    创建订阅 API Client
    """

    action: ClassVar[str] = "create_subscription"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "subscription_create/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/create/"


class UpdateSubscription(NodeManApiClient):
    """
    更新订阅 API Client
    """

    action: ClassVar[str] = "update_subscription"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "subscription_update/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/update/"


class RetrySubscription(NodeManApiClient):
    """
    重试订阅 API Client
    """

    action: ClassVar[str] = "retry_subscription"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "backend/api/subscription/retry/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/retry/"


class RevokeSubscription(NodeManApiClient):
    """
    终止订阅 API Client
    """

    action: ClassVar[str] = "revoke_subscription"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "backend/api/subscription/revoke/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/revoke/"


class GetSubscriptionInfo(NodeManApiClient):
    """
    获取订阅信息 API Client
    """

    action: ClassVar[str] = "get_subscription_info"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "subscription_info/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/info/"


class GetSubscriptionTaskResultDetail(NodeManApiClient):
    """
    获取订阅任务结果详情 API Client
    """

    action: ClassVar[str] = "get_subscription_task_result_detail"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "subscription_task_result_detail/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/task_result_detail/"


class GetSubscriptionTaskResult(NodeManApiClient):
    """
    获取订阅任务结果 API Client
    """

    action: ClassVar[str] = "get_subscription_task_result"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "subscription_task_result/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/task_result/"


class GetProxies(NodeManControlApiClient):
    """
    【节点管理2.0】查询云区域下的proxy列表
    """

    action: ClassVar[str] = "get_proxies"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "api/host/proxies/"
    apigw_path: ClassVar[str] = "system/api/host/proxies/"


class GetProxiesByBiz(NodeManControlApiClient):
    """
    【节点管理2.0】通过业务查询业务所使用的所有云区域下的ProxyIP
    """

    action: ClassVar[str] = "get_proxies_by_biz"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "api/host/biz_proxies/"
    apigw_path: ClassVar[str] = "system/api/host/biz_proxies/"


class PluginOperate(NodeManApiClient):
    """
    【节点管理2.0】插件管理接口
    """

    action: ClassVar[str] = "plugin_operate"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "api/plugin/operate/"
    apigw_path: ClassVar[str] = "system/api/plugin/operate/"


class OfficialPluginOperate(PluginOperate, NodeManControlApiClient):
    """官方插件控制入口；采集器自动部署仍通过 PluginOperate 使用 V2。"""


class PluginSearch(NodeManApiClient):
    """
    【节点管理2.0】插件查询接口
    """

    action: ClassVar[str] = "plugin_search"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "api/plugin/search/"
    apigw_path: ClassVar[str] = "system/api/plugin/search/"


class SubscriptionCheckTaskReady(NodeManApiClient):
    """
    【节点管理2.1】检查订阅任务是否准备就绪 API Client
    """

    action: ClassVar[str] = "subscription_check_task_ready"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "backend/api/subscription/check_task_ready/"
    apigw_path: ClassVar[str] = "system/backend/api/subscription/check_task_ready/"


class IpchooserHostDetails(NodeManControlApiClient):
    """
    查询主机详情 API Client
    """

    action: ClassVar[str] = "ipchooser_host_details"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "core/api/ipchooser_host/details/"
    apigw_path: ClassVar[str] = "core/api/ipchooser_host/details/"


upload_plugin_client = UploadPlugin()
create_register_plugin_task_client = CreateRegisterPluginTask()
query_register_plugin_task_client = QueryRegisterPluginTask()
get_plugin_info_client = GetPluginInfo()
release_plugin_client = ReleasePlugin()
create_plugin_config_template_client = CreatePluginConfigTemplate()
release_plugin_config_template_client = ReleasePluginConfigTemplate()
create_export_plugin_task_client = CreateExportPluginTask()
query_export_plugin_task_client = QueryExportPluginTask()
start_plugin_debug_client = StartPluginDebug()
query_plugin_debug_client = QueryPluginDebug()
stop_plugin_debug_client = StopPluginDebug()
render_plugin_config_template_client = RenderPluginConfigTemplate()

switch_subscription_client = SwitchSubscription()
run_subscription_client = RunSubscription()
create_subscription_client = CreateSubscription()
update_subscription_client = UpdateSubscription()
retry_subscription_client = RetrySubscription()
revoke_subscription_client = RevokeSubscription()
get_subscription_info_client = GetSubscriptionInfo()
get_subscription_task_result_detail_client = GetSubscriptionTaskResultDetail()
get_subscription_task_result_client = GetSubscriptionTaskResult()
get_proxies_client = GetProxies()
get_proxies_by_biz_client = GetProxiesByBiz()
plugin_operate_client = PluginOperate()
official_plugin_operate_client = OfficialPluginOperate()
plugin_search_client = PluginSearch()
subscription_check_task_ready_client = SubscriptionCheckTaskReady()
ipchooser_host_details_client = IpchooserHostDetails()
