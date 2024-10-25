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
from rest_framework import permissions

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class CollectingConfigViewSet(ResourceViewSet):
    iam_read_actions = ActionEnum.VIEW_COLLECTION
    iam_write_actions = ActionEnum.MANAGE_COLLECTION

    query_post_actions = ["config_list", "graph_point", "target_status_topo", "get_collect_dashboard_config"]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS or self.action in self.query_post_actions:
            return [BusinessActionPermission([ActionEnum.VIEW_COLLECTION])]
        return [BusinessActionPermission([ActionEnum.MANAGE_COLLECTION])]

    resource_routes = [
        # 获取采集配置列表信息
        ResourceRoute("POST", resource.collecting.collect_config_list, endpoint="config_list"),
        # 获取采集配置详情信息
        ResourceRoute("GET", resource.collecting.collect_config_detail, endpoint="config_detail"),
        # 启停采集配置
        ResourceRoute("POST", resource.collecting.toggle_collect_config_status, endpoint="toggle"),
        # 删除采集配置
        ResourceRoute("POST", resource.collecting.delete_collect_config, endpoint="delete"),
        # 克隆采集配置
        ResourceRoute("POST", resource.collecting.clone_collect_config, endpoint="clone"),
        # 重试部分实例或主机
        ResourceRoute("POST", resource.collecting.retry_target_nodes, endpoint="retry"),
        # 终止部分实例或主机
        ResourceRoute("POST", resource.collecting.revoke_target_nodes, endpoint="revoke"),
        # 批量终止实例或主机
        ResourceRoute("POST", resource.collecting.batch_revoke_target_nodes, endpoint="batch_revoke"),
        # 批量重试采集配置的失败实例
        ResourceRoute("POST", resource.collecting.batch_retry_config, endpoint="batch_retry"),
        # 新建/编辑采集配置
        ResourceRoute("POST", resource.collecting.save_collect_config, endpoint="save"),
        # 采集配置插件升级
        ResourceRoute("POST", resource.collecting.upgrade_collect_plugin, endpoint="upgrade"),
        # 采集配置回滚
        ResourceRoute("POST", resource.collecting.rollback_deployment_config, endpoint="rollback"),
        # 获取采集对象和状态（采集视图侧边栏）
        ResourceRoute("POST", resource.collecting.frontend_target_status_topo, endpoint="target_status_topo"),
        # 获取采集配置详情信息(前端接口)
        ResourceRoute("GET", resource.collecting.frontend_collect_config_detail, endpoint="frontend_config_detail"),
        # 获取采集目标信息(前端接口)
        ResourceRoute("GET", resource.collecting.frontend_collect_config_target_info, endpoint="frontend_target_info"),
        # 配置执行详情列表接口（被datalink模块使用，对数据进行二次加工，用于策略详情展示）
        ResourceRoute("GET", resource.collecting.collect_instance_status, endpoint="collect_instance_status"),
        # 获取采集下发状态（状态轮询）
        ResourceRoute("GET", resource.collecting.collect_target_status, endpoint="status"),
        # 获取对应插件版本的指标参数
        ResourceRoute("GET", resource.collecting.get_metrics, endpoint="metrics"),
        # 采集配置名称修改
        ResourceRoute("POST", resource.collecting.rename_collect_config, endpoint="rename"),
        # 获取采集配置的部署配置差异
        ResourceRoute("GET", resource.collecting.deployment_config_diff, endpoint="deployment_diff"),
        # 获取采集配置主机的运行状态（启停前预览）
        ResourceRoute("GET", resource.collecting.collect_running_status, endpoint="running_status"),
        # 获取采集下发详细日志
        ResourceRoute("GET", resource.collecting.get_collect_log_detail, endpoint="get_collect_log_detail"),
        # 获取采集配置变量列表
        ResourceRoute("GET", resource.collecting.get_collect_variables, endpoint="get_collect_variables"),
        # 执行详情页批量重试
        ResourceRoute("POST", resource.collecting.batch_retry, endpoint="batch_retry_detailed"),
        # toolkit
        # 获取各个采集项遗留的订阅配置及节点管理无效的订阅任务
        ResourceRoute("GET", resource.collecting.list_legacy_subscription, endpoint="list_legacy_subscription"),
        # 停用并删除遗留的订阅配置
        ResourceRoute("GET", resource.collecting.clean_legacy_subscription, endpoint="clean_legacy_subscription"),
        # 列出当前无效的告警策略
        ResourceRoute("GET", resource.collecting.list_legacy_strategy, endpoint="list_legacy_strategy"),
        # 列出指定采集配置的关联策略
        ResourceRoute("POST", resource.collecting.list_related_strategy, endpoint="list_related_strategy"),
        # 向节点管理轮询任务是否已经初始化完成
        ResourceRoute("POST", resource.collecting.is_task_ready, endpoint="is_task_ready"),
        # 检查游离态采集配置
        ResourceRoute("GET", resource.collecting.check_adjective_collect, endpoint="check_adjective_collect"),
        # 获取采集配置列表统计信息
        ResourceRoute("GET", resource.collecting.fetch_collect_config_stat, endpoint="fetch_collect_config_stat"),
        # 依赖插件版本前置校验
        ResourceRoute("POST", resource.collecting.check_plugin_version, endpoint="check_plugin_version"),
    ]
