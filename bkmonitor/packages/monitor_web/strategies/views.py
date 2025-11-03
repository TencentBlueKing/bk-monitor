"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import permissions

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission, ViewBusinessPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class StrategiesViewSet(ResourceViewSet):
    iam_read_actions = ActionEnum.VIEW_RULE
    iam_write_actions = ActionEnum.MANAGE_RULE

    def get_permissions(self):
        if self.action in [
            "get_unit_list",
            "get_scenario_list",
            "strategy_label",
            "strategy_label_list",
            "delete_strategy_label",
            # 策略订阅暂时不设置权限
            "subscribe/save",
            "subscribe/delete",
            "subscribe/list",
            "subscribe/detail",
        ]:
            return []
        if self.action in [
            "fetch_item_status",
            "query_config_to_promql",
            "promql_to_query_config",
        ]:
            return [ViewBusinessPermission()]
        if self.action in [
            "strategy_config_list",
            "v2/get_strategy_list",
            "get_target_detail",
            "dashboard_panel_to_query_config",
        ]:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE])]
        if self.action in [
            "get_metric_list",
            "v2/get_metric_list",
            "update_metric_list_by_biz",
        ]:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE, ActionEnum.EXPLORE_METRIC])]
        if self.action in ["v2/get_plain_strategy_list"]:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE, ActionEnum.VIEW_DOWNTIME])]
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE])]
        return [BusinessActionPermission([ActionEnum.MANAGE_RULE])]

    resource_routes = [
        # common
        # 获取全部监控场景
        ResourceRoute("GET", resource.strategies.get_scenario_list, endpoint="get_scenario_list"),
        # 获取模板变量列表
        ResourceRoute("GET", resource.strategies.notice_variable_list, endpoint="notice_variable_list"),
        # 获取动态单位列表
        ResourceRoute("GET", resource.strategies.get_unit_list, endpoint="get_unit_list"),
        # 获取单位详情
        ResourceRoute("GET", resource.strategies.get_unit_info, endpoint="get_unit_info"),
        # 创建、修改策略标签
        ResourceRoute("POST", resource.strategies.strategy_label, endpoint="strategy_label"),
        # 获取策略标签列表
        ResourceRoute("GET", resource.strategies.strategy_label_list, endpoint="strategy_label_list"),
        # 删除策略标签
        ResourceRoute("POST", resource.strategies.delete_strategy_label, endpoint="delete_strategy_label"),
        # 查询指标策略配置及告警情况
        ResourceRoute("POST", resource.strategies.fetch_item_status, endpoint="fetch_item_status"),
        # 获取策略目标详情
        ResourceRoute("POST", resource.strategies.get_target_detail, endpoint="get_target_detail"),
        # v1 - 旧版接口
        # 获取全部监控指标， 已下线
        ResourceRoute("POST", resource.strategies.get_metric_list, endpoint="get_metric_list"),
        # 获取指标维度最近所上报的值
        ResourceRoute("POST", resource.strategies.get_dimension_values, endpoint="get_dimension_values"),
        # 创建、修改监控策略
        ResourceRoute("POST", resource.strategies.strategy_config, endpoint="strategy_config"),
        # 拷贝监控策略
        ResourceRoute("POST", resource.strategies.clone_strategy_config, endpoint="clone_strategy_config"),
        # 删除监控策略
        ResourceRoute("POST", resource.strategies.delete_strategy_config, endpoint="delete_strategy_config"),
        # 获取监控策略列表
        ResourceRoute("POST", resource.strategies.strategy_config_list, endpoint="strategy_config_list"),
        # 获取监控策略详情
        ResourceRoute("GET", resource.strategies.strategy_config_detail, endpoint="strategy_config_detail"),
        # 批量修改策略接口
        ResourceRoute("POST", resource.strategies.bulk_edit_strategy, endpoint="bulk_edit_strategy"),
        # 获取指标的维度列表
        ResourceRoute("GET", resource.strategies.get_dimension_list, endpoint="get_dimension_list"),
        # 获取监控策略轻量列表
        ResourceRoute("GET", resource.strategies.plain_strategy_list, endpoint="plain_strategy_list"),
        # 获取监控策略信息
        ResourceRoute("GET", resource.strategies.strategy_info, endpoint="strategy_info"),
        # 获取索引列表
        ResourceRoute("GET", resource.strategies.get_index_set_list, endpoint="get_index_set_list"),
        # 获取索引field
        ResourceRoute("GET", resource.strategies.get_log_fields, endpoint="get_log_fields"),
        # v2 - 新版接口
        # 获取全部监控指标
        ResourceRoute("POST", resource.strategies.get_metric_list_v2, endpoint="v2/get_metric_list"),
        # 获取策略列表
        ResourceRoute("POST", resource.strategies.get_strategy_list_v2, endpoint="v2/get_strategy_list"),
        # 获取策略详情
        ResourceRoute("GET", resource.strategies.get_strategy_v2, endpoint="v2/get_strategy"),
        # 删除策略
        ResourceRoute("POST", resource.strategies.delete_strategy_v2, endpoint="v2/delete_strategy"),
        # 校验策略名
        ResourceRoute("POST", resource.strategies.verify_strategy_name, endpoint="v2/verify_strategy_name"),
        # 保存/创建策略
        ResourceRoute("POST", resource.strategies.save_strategy_v2, endpoint="v2/save_strategy"),
        # 批量更新策略
        ResourceRoute("POST", resource.strategies.update_partial_strategy_v2, endpoint="v2/update_partial_strategy"),
        # 克隆策略
        ResourceRoute("POST", resource.strategies.clone_strategy_v2, endpoint="v2/clone_strategy"),
        # 获取简版策略列表
        ResourceRoute("GET", resource.strategies.get_plain_strategy_list_v2, endpoint="v2/get_plain_strategy_list"),
        # 查询配置转换为PromQL
        ResourceRoute("POST", resource.strategies.query_config_to_promql, endpoint="query_config_to_promql"),
        # PromQL转为查询配置
        ResourceRoute("POST", resource.strategies.promql_to_query_config, endpoint="promql_to_query_config"),
        # 获取模型列表
        ResourceRoute("GET", resource.strategies.list_intelligent_models, endpoint="list_intelligent_models"),
        # 获取单个模型详情
        ResourceRoute("GET", resource.strategies.get_intelligent_model, endpoint="get_intelligent_model"),
        # 获取单个模型状态
        ResourceRoute(
            "GET", resource.strategies.get_intelligent_model_task_status, endpoint="get_intelligent_model_task_status"
        ),
        # 获取单个模型状态
        ResourceRoute(
            "GET",
            resource.strategies.get_intelligent_detect_access_status,
            endpoint="get_intelligent_detect_access_status",
        ),
        # 按业务更新指标缓存列表
        ResourceRoute("POST", resource.strategies.update_metric_list_by_biz, endpoint="update_metric_list_by_biz"),
        # 获取单位详情
        ResourceRoute("GET", resource.strategies.multivariate_anomaly_scenes, endpoint="multivariate_anomaly_scenes"),
        # 将仪表盘图表转换为查询配置
        ResourceRoute(
            "POST", resource.strategies.dashboard_panel_to_query_config, endpoint="dashboard_panel_to_query_config"
        ),
        # 返回简易版本的策略列表
        ResourceRoute("GET", resource.strategies.get_devops_strategy_list, endpoint="get_devops_strategy_list"),
        # 新增/保存策略订阅
        ResourceRoute("POST", resource.strategies.save_strategy_subscribe, endpoint="subscribe/save"),
        # 删除策略订阅
        ResourceRoute("POST", resource.strategies.delete_strategy_subscribe, endpoint="subscribe/delete"),
        # 获取策略订阅列表
        ResourceRoute("GET", resource.strategies.list_strategy_subscribe, endpoint="subscribe/list"),
        # 获取策略订阅详情
        ResourceRoute("GET", resource.strategies.detail_strategy_subscribe, endpoint="subscribe/detail"),
        # 批量新增/保存策略订阅
        ResourceRoute("POST", resource.strategies.bulk_save_strategy_subscribe, endpoint="subscribe/bulk_save"),
        # 批量删除策略订阅
        ResourceRoute("POST", resource.strategies.bulk_delete_strategy_subscribe, endpoint="subscribe/bulk_delete"),
    ]
