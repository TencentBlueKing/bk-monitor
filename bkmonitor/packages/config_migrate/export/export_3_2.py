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
import json
import os
import shutil
import subprocess
import tempfile

from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    CustomEventGroup,
    CustomTSTable,
)

from bkmonitor.models import NoticeGroup
from bkmonitor.strategy.strategy import Strategy, StrategyConfig
from core.drf_resource import api


def export_config(bk_biz_id: int):
    """
    workon bkmonitorv3-monitor
    source bin/environ.sh
    export DJANGO_CONF_MODULE=conf.api.production.enterprise
    export BKAPP_GRAFANA_URL=http://127.0.0.1:3000
    """
    custom_events = {}
    for event in CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id, is_enable=True, type="custom_event"):
        custom_events[event.bk_event_group_id] = {
            "bk_event_group_id": event.bk_event_group_id,
            "bk_data_id": event.bk_data_id,
            "name": event.name,
            "scenario": event.scenario,
            "table_id": event.table_id,
            "type": event.type,
            "is_platform": False,
        }

    custom_metrics = {}
    for metric in CustomTSTable.objects.filter(bk_biz_id=bk_biz_id):
        custom_metrics[metric.time_series_group_id] = {
            "time_series_group_id": metric.time_series_group_id,
            "bk_data_id": metric.bk_data_id,
            "name": metric.name,
            "scenario": metric.scenario,
            "table_id": metric.table_id,
            "is_platform": False,
            "protocol": "json",
            "desc": metric.desc,
        }

    # 获取所有通知组
    notice_groups = {}
    for notice_group in NoticeGroup.objects.filter(bk_biz_id=bk_biz_id).only("id", "bk_biz_id"):
        notice_groups[notice_group.id] = {
            "bk_biz_id": notice_group.bk_biz_id,
            "name": notice_group.name,
            "id": notice_group.id,
            "message": notice_group.message,
            "notice_way": notice_group.notice_way,
            "notice_receiver": notice_group.notice_receiver,
            "webhook_url": notice_group.webhook_url,
            "wxwork_group": notice_group.wxwork_group,
        }

    # 获取所有策略
    strategies = {}
    for strategy in Strategy.objects.filter(bk_biz_id=bk_biz_id).only("id", "bk_biz_id"):
        strategies[strategy.id] = StrategyConfig(strategy.bk_biz_id, strategy.id).strategy_dict

    # 获取所有仪表盘
    dashboards = {}
    org = api.grafana.get_organization_by_name(name=str(bk_biz_id))
    if not org["result"]:
        raise Exception("org not found")
    org_id = org["data"]["id"]
    for dashboard in api.grafana.search_folder_or_dashboard(org_id=org_id, type="dash-db")["data"]:
        dc = api.grafana.get_dashboard_by_uid(org_id=org_id, uid=dashboard["uid"])["data"]
        if dashboard.get("folderTitle"):
            dc["folderTitle"] = dashboard["folderTitle"]
        dashboards[dashboard["uri"].split("/")[-1]] = api.grafana.get_dashboard_by_uid(
            org_id=org_id, uid=dashboard["uid"]
        )["data"]["dashboard"]

    collects = {}
    for collect_meta in CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id).select_related("deployment_config"):
        collects[collect_meta.id] = {
            "id": collect_meta.id,
            "name": collect_meta.name,
            "collect_type": collect_meta.collect_type,
            "label": collect_meta.label,
            "target_object_type": collect_meta.target_object_type,
            "target_node_type": collect_meta.deployment_config.target_node_type,
            "target_nodes": collect_meta.deployment_config.target_nodes,
            "params": collect_meta.deployment_config.params,
            "plugin_id": collect_meta.plugin_id,
            "label_info": collect_meta.label_info,
        }

    plugins = {"plugin": []}
    for plugin in CollectorPluginMeta.objects.filter(bk_biz_id=bk_biz_id):
        plugins[plugin.plugin_id] = plugin.get_plugin_detail()

    # 打包配置
    with tempfile.TemporaryDirectory() as tmpdirname:
        data_mapping = {
            "strategy": strategies,
            "notice_group": notice_groups,
            "dashboard": dashboards,
            "custom_metric": custom_metrics,
            "custom_event": custom_events,
            "collect": collects,
            "plugin": plugins,
        }

        for name, configs in data_mapping.items():
            os.mkdir(os.path.join(tmpdirname, name))
            for config_name, config in configs.items():
                with open(os.path.join(tmpdirname, name, f"{config_name}.json"), "w") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

        # 打包
        subprocess.run(["tar", "-zcvf", f"config_{bk_biz_id}.tar.gz", *data_mapping.keys()], cwd=tmpdirname)

        # 复制
        shutil.copy(os.path.join(tmpdirname, f"config_{bk_biz_id}.tar.gz"), f"/tmp/config_{bk_biz_id}.tar.gz")
