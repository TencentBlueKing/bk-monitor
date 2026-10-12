"""蓝鲸监控 V3 API 客户端封装。"""

from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class BkMonitorV3ApiClient(BkApiClient, ABC):
    """
    监控平台 API Client
    """

    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "bk_monitorv3"
    esb_base_url: ClassVar[str] = ""
    esb_path: ClassVar[str] = ""
    apigw_base_url: ClassVar[str] = "api/bk-monitor/prod/"

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        result = super().handle_response(response)
        # 监控平台 API 通常直接返回数据，不需要额外处理
        return result.get("data", result)


class GetTraceViewConfig(BkMonitorV3ApiClient):
    """获取 trace 查询视图配置。"""

    action: ClassVar[str] = "get_trace_view_config"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/apm/view_config/"


class GetFieldsOptionValues(BkMonitorV3ApiClient):
    """获取 trace 字段可选值。"""

    action: ClassVar[str] = "get_fields_option_values"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/apm/get_fields_option_values/"


class CustomTimeSeriesDetail(BkMonitorV3ApiClient):
    """获取自定义时序详情。"""

    action: ClassVar[str] = "custom_time_series_detail"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/custom_metric/detail/"


class SaveAlarmStrategy(BkMonitorV3ApiClient):
    """保存告警策略。"""

    action: ClassVar[str] = "save_alarm_strategy_v3"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "save_alarm_strategy_v3"
    apigw_path: ClassVar[str] = "app/alarm_strategy/save/"


class SaveAlarmStrategyV2(BkMonitorV3ApiClient):
    """保存告警策略 V2。"""

    action: ClassVar[str] = "save_alarm_strategy_v2"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "save_alarm_strategy_v2"
    apigw_path: ClassVar[str] = "app/alarm_strategy/save/v2/"


class DeleteAlarmStrategy(BkMonitorV3ApiClient):
    """删除告警策略。"""

    action: ClassVar[str] = "delete_alarm_strategy_v3"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "delete_alarm_strategy_v3"
    apigw_path: ClassVar[str] = "app/alarm_strategy/delete/"


class SearchAlarmStrategy(BkMonitorV3ApiClient):
    """查询告警策略列表。"""

    action: ClassVar[str] = "search_alarm_strategy_v3"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_alarm_strategy_v3"
    apigw_path: ClassVar[str] = "app/alarm_strategy/search/"


class SwitchAlarmStrategy(BkMonitorV3ApiClient):
    """启停告警策略。"""

    action: ClassVar[str] = "switch_alarm_strategy"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "switch_alarm_strategy"
    apigw_path: ClassVar[str] = "app/alarm_strategy/switch/"


class SaveCollectConfig(BkMonitorV3ApiClient):
    """保存采集配置。"""

    action: ClassVar[str] = "save_collect_config"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "save_collect_config"
    apigw_path: ClassVar[str] = "app/collect_config/save/"


class DeleteCollectConfig(BkMonitorV3ApiClient):
    """删除采集配置。"""

    action: ClassVar[str] = "delete_collect_config"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "delete_collect_config"
    apigw_path: ClassVar[str] = "app/collect_config/delete/"


class ListCollectConfig(BkMonitorV3ApiClient):
    """查询采集配置列表。"""

    action: ClassVar[str] = "list_collect_config"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "list_collect_config"
    apigw_path: ClassVar[str] = "app/collect_config/list/"


class DetailCollectConfig(BkMonitorV3ApiClient):
    """查询采集配置详情。"""

    action: ClassVar[str] = "detail_collect_config"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "frontend_collect_config_detail"
    apigw_path: ClassVar[str] = "app/collect_config/detail/"


class RunCollectConfig(BkMonitorV3ApiClient):
    """运行采集配置。"""

    action: ClassVar[str] = "run_collect_config"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "run_collect_config"
    apigw_path: ClassVar[str] = "app/collect_config/run/"


class ToggleCollectConfig(BkMonitorV3ApiClient):
    """切换采集配置状态。"""

    action: ClassVar[str] = "toggle_collect_config"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "toggle_collect_config_status"
    apigw_path: ClassVar[str] = "app/collect_config/toggle/"


class ListCollectorPlugins(BkMonitorV3ApiClient):
    """查询采集插件列表。"""

    action: ClassVar[str] = "collector_plugin_list"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "collector_plugin_list"
    apigw_path: ClassVar[str] = "app/plugin/list/"


class GetCollectorPluginDetail(BkMonitorV3ApiClient):
    """查询采集插件详情。"""

    action: ClassVar[str] = "collector_plugin_detail"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "collector_plugin_detail"
    apigw_path: ClassVar[str] = "app/plugin/detail/"


class DeleteCollectorPlugin(BkMonitorV3ApiClient):
    """删除采集插件。"""

    action: ClassVar[str] = "collector_plugin_delete"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "collector_plugin_delete"
    apigw_path: ClassVar[str] = "app/plugin/delete/"


class GetCollectorPluginUpgradeInfo(BkMonitorV3ApiClient):
    """查询采集插件升级信息。"""

    action: ClassVar[str] = "collector_plugin_upgrade_info"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "collector_plugin_upgrade_info"
    apigw_path: ClassVar[str] = "app/plugin/upgrade_info/"


class UpgradeCollectPlugin(BkMonitorV3ApiClient):
    """升级采集插件。"""

    action: ClassVar[str] = "upgrade_collect_plugin"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "upgrade_collect_plugin"
    apigw_path: ClassVar[str] = "app/collect_config/upgrade/"


class SaveNoticeGroup(BkMonitorV3ApiClient):
    """保存通知组。"""

    action: ClassVar[str] = "save_notice_group"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "save_notice_group"
    apigw_path: ClassVar[str] = "app/legacy/save_notice_group/"


class DeleteNoticeGroup(BkMonitorV3ApiClient):
    """删除通知组。"""

    action: ClassVar[str] = "delete_notice_group"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "delete_notice_group"
    apigw_path: ClassVar[str] = "app/legacy/delete_notice_group/"


class SearchAlert(BkMonitorV3ApiClient):
    """查询告警列表。"""

    action: ClassVar[str] = "search_alert"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_alert"
    apigw_path: ClassVar[str] = "app/alert/search/"


class DetailAlert(BkMonitorV3ApiClient):
    """查询告警详情。"""

    action: ClassVar[str] = "detail_alert"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "alert_detail"
    apigw_path: ClassVar[str] = "app/alert/detail/"


class TestUptimeCheckTask(BkMonitorV3ApiClient):
    """测试拨测任务。"""

    action: ClassVar[str] = "test_uptime_check_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "test_uptime_check_task"
    apigw_path: ClassVar[str] = "app/uptime_check/task/test/"


class CreateUptimeCheckTask(BkMonitorV3ApiClient):
    """创建拨测任务。"""

    action: ClassVar[str] = "create_uptime_check_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "create_uptime_check_task"
    apigw_path: ClassVar[str] = "app/uptime_check/task/create/"


class EditUptimeCheckTask(BkMonitorV3ApiClient):
    """编辑拨测任务。"""

    action: ClassVar[str] = "edit_uptime_check_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "edit_uptime_check_task"
    apigw_path: ClassVar[str] = "app/uptime_check/task/edit/"


class DeleteUptimeCheckTask(BkMonitorV3ApiClient):
    """删除拨测任务。"""

    action: ClassVar[str] = "delete_uptime_check_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "delete_uptime_check_task"
    apigw_path: ClassVar[str] = "app/uptime_check/task/delete/"


class DeployUptimeCheckTask(BkMonitorV3ApiClient):
    """下发拨测任务。"""

    action: ClassVar[str] = "deploy_uptime_check_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "deploy_uptime_check_task"
    apigw_path: ClassVar[str] = "app/uptime_check/task/deploy/"


class ChangeUptimeCheckTaskStatus(BkMonitorV3ApiClient):
    """修改拨测任务状态。"""

    action: ClassVar[str] = "change_uptime_check_task_status"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "change_uptime_check_task_status"
    apigw_path: ClassVar[str] = "app/uptime_check/task/change_status/"


class GetUptimeCheckTaskList(BkMonitorV3ApiClient):
    """获取拨测任务列表。"""

    action: ClassVar[str] = "get_uptime_check_task_list"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "get_uptime_check_task_list"
    apigw_path: ClassVar[str] = "app/uptime_check/task/list/"


class GetUptimeCheckNodeList(BkMonitorV3ApiClient):
    """获取拨测节点列表。"""

    action: ClassVar[str] = "get_uptime_check_node_list"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "get_uptime_check_node_list"
    apigw_path: ClassVar[str] = "app/uptime_check/node/list/"


class CreateUptimeCheckNode(BkMonitorV3ApiClient):
    """创建拨测节点。"""

    action: ClassVar[str] = "create_uptime_check_node"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "create_uptime_check_node"
    apigw_path: ClassVar[str] = "app/uptime_check/node/create/"


class EditUptimeCheckNode(BkMonitorV3ApiClient):
    """编辑拨测节点。"""

    action: ClassVar[str] = "edit_uptime_check_node"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "edit_uptime_check_node"
    apigw_path: ClassVar[str] = "app/uptime_check/node/edit/"


class DeleteUptimeCheckNode(BkMonitorV3ApiClient):
    """删除拨测节点。"""

    action: ClassVar[str] = "delete_uptime_check_node"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "delete_uptime_check_node"
    apigw_path: ClassVar[str] = "app/uptime_check/node/delete/"


class ImportUptimeCheckNode(BkMonitorV3ApiClient):
    """导入拨测节点。"""

    action: ClassVar[str] = "import_uptime_check_node"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "import_uptime_check_node"
    apigw_path: ClassVar[str] = "app/uptime_check/node/import/"


class ImportUptimeCheckTask(BkMonitorV3ApiClient):
    """导入拨测任务。"""

    action: ClassVar[str] = "import_uptime_check_task"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "import_uptime_check_task"
    apigw_path: ClassVar[str] = "app/uptime_check/task/import/"


class ExportUptimeCheckTask(BkMonitorV3ApiClient):
    """导出拨测任务。"""

    action: ClassVar[str] = "export_uptime_check_task"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "export_uptime_check_task"
    apigw_path: ClassVar[str] = "app/uptime_check/task/export/"


get_trace_view_config_client: GetTraceViewConfig = GetTraceViewConfig()
get_fields_option_values_client: GetFieldsOptionValues = GetFieldsOptionValues()
custom_time_series_detail_client: CustomTimeSeriesDetail = CustomTimeSeriesDetail()

save_alarm_strategy_client: SaveAlarmStrategy = SaveAlarmStrategy()
save_alarm_strategy_v2_client: SaveAlarmStrategyV2 = SaveAlarmStrategyV2()
delete_alarm_strategy_client: DeleteAlarmStrategy = DeleteAlarmStrategy()
search_alarm_strategy_client: SearchAlarmStrategy = SearchAlarmStrategy()
switch_alarm_strategy_client: SwitchAlarmStrategy = SwitchAlarmStrategy()

save_collect_config_client: SaveCollectConfig = SaveCollectConfig()
delete_collect_config_client: DeleteCollectConfig = DeleteCollectConfig()
list_collect_config_client: ListCollectConfig = ListCollectConfig()
detail_collect_config_client: DetailCollectConfig = DetailCollectConfig()
run_collect_config_client: RunCollectConfig = RunCollectConfig()
toggle_collect_config_client: ToggleCollectConfig = ToggleCollectConfig()

save_notice_group_client: SaveNoticeGroup = SaveNoticeGroup()
delete_notice_group_client: DeleteNoticeGroup = DeleteNoticeGroup()

search_alert_client: SearchAlert = SearchAlert()
detail_alert_client: DetailAlert = DetailAlert()

test_uptime_check_task_client: TestUptimeCheckTask = TestUptimeCheckTask()
create_uptime_check_task_client: CreateUptimeCheckTask = CreateUptimeCheckTask()
edit_uptime_check_task_client: EditUptimeCheckTask = EditUptimeCheckTask()
delete_uptime_check_task_client: DeleteUptimeCheckTask = DeleteUptimeCheckTask()
deploy_uptime_check_task_client: DeployUptimeCheckTask = DeployUptimeCheckTask()
change_uptime_check_task_status_client: ChangeUptimeCheckTaskStatus = ChangeUptimeCheckTaskStatus()
get_uptime_check_task_list_client: GetUptimeCheckTaskList = GetUptimeCheckTaskList()
get_uptime_check_node_list_client: GetUptimeCheckNodeList = GetUptimeCheckNodeList()
create_uptime_check_node_client: CreateUptimeCheckNode = CreateUptimeCheckNode()
edit_uptime_check_node_client: EditUptimeCheckNode = EditUptimeCheckNode()
delete_uptime_check_node_client: DeleteUptimeCheckNode = DeleteUptimeCheckNode()
import_uptime_check_node_client: ImportUptimeCheckNode = ImportUptimeCheckNode()
import_uptime_check_task_client: ImportUptimeCheckTask = ImportUptimeCheckTask()
export_uptime_check_task_client: ExportUptimeCheckTask = ExportUptimeCheckTask()

list_collector_plugins_client: ListCollectorPlugins = ListCollectorPlugins()
get_collector_plugin_detail_client: GetCollectorPluginDetail = GetCollectorPluginDetail()
delete_collector_plugin_client: DeleteCollectorPlugin = DeleteCollectorPlugin()
get_collector_plugin_upgrade_info_client: GetCollectorPluginUpgradeInfo = GetCollectorPluginUpgradeInfo()
upgrade_collect_plugin_client: UpgradeCollectPlugin = UpgradeCollectPlugin()
