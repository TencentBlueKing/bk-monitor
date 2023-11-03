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
import logging
import os

from blueapps.conf import settings
from monitor_web.grafana.utils import patch_home_panels

from bk_dataview.provisioning import SimpleProvisioning, Datasource, sync_data_sources
from bkmonitor.commons.tools import is_ipv6_biz
from core.drf_resource import api

logger = logging.getLogger(__name__)


class BkMonitorProvisioning(SimpleProvisioning):
    def dashboards(self, request, org_name: str, org_id: int):
        """
        只执行一次
        """
        from monitor.models import ApplicationConfig

        grafana_default_dashboard_name = ["host-ipv6" if is_ipv6_biz(org_name) else "host", "observable"]

        # 如果是如果存在BCS相关配置，则注入容器相关面板
        if settings.BCS_API_GATEWAY_HOST:
            grafana_default_dashboard_name += [
                "kubernetes-b-工作节点-Kubelet",
                "kubernetes-b-工作节点-Node",
                "kubernetes-b-集群组件-Kube-proxy",
                "kubernetes集群资源-Cluster",
                "kubernetes集群资源-NameSpace",
                "kubernetes集群资源-Pod",
                "Distributed-Tracing"
            ]

        # 如果已经执行过默认面板注入操作，则不注入
        grafana_default_dashboard_map = {}
        grafana_default_dashboard_key = set()
        for dashboard in grafana_default_dashboard_name:
            key = f"grafana_default_dashboard_{dashboard}"
            if dashboard == "host":
                key = "grafana_default_dashboard"
            grafana_default_dashboard_key.add(key)
            grafana_default_dashboard_map[key] = dashboard
        created = set(
            ApplicationConfig.objects.filter(
                key__in=grafana_default_dashboard_key, cc_biz_id=org_name, value="created"
            ).values_list("key", flat=True)
        )
        not_created = grafana_default_dashboard_key - created
        for i in not_created:
            if self.create_default_dashboard(org_id, f"{grafana_default_dashboard_map[i]}.json"):
                ApplicationConfig.objects.get_or_create(cc_biz_id=org_name, key=i, value="created")
        logger.info("monitor grafana, {}".format(not_created))
        yield from []

    @staticmethod
    def create_default_dashboard(org_id, json_name="host.json", folder_id=0, bk_biz_id=None):
        """
        创建仪表盘，并且设置为组织默认仪表盘
        :param org_id: 组织ID
        :type org_id: int
        :param json_name: 配置文件名
        :type json_name: string
        :param folder_id: 目录 id
        :param bk_biz_id: 业务 id ==> org_name
        """
        data_sources = {
            data_source["type"]: {
                "type": "datasource",
                "pluginId": data_source["type"],
                "value": data_source.get("uid", ""),
            }
            for data_source in api.grafana.get_all_data_source(org_id=org_id)["data"]
        }
        if not data_sources:
            org_name = str(bk_biz_id)
            provisioning = SimpleProvisioning()
            ds_list = []
            for ds in provisioning.datasources(None, org_name, org_id):
                if not isinstance(ds, Datasource):
                    raise ValueError("{} is not instance {}".format(type(ds), Datasource))
                ds_list.append(ds)
            sync_data_sources(org_id, ds_list)
            data_sources = {
                data_source["type"]: {
                    "type": "datasource",
                    "pluginId": data_source["type"],
                    "value": data_source.get("uid", ""),
                }
                for data_source in api.grafana.get_all_data_source(org_id=org_id)["data"]
            }

        path = os.path.join(settings.BASE_DIR, f"packages/monitor_web/grafana/dashboards/{json_name}")
        try:
            with open(path, encoding="utf-8") as f:
                dashboard_config = json.loads(f.read())
                if json_name == "home.json":
                    dashboard_config["panels"] = patch_home_panels()

            inputs = []
            for input_field in dashboard_config.get("__inputs", []):
                if input_field["type"] != "datasource" or input_field["pluginId"] not in data_sources:
                    continue
                inputs.append({"name": input_field["name"], **data_sources[input_field["pluginId"]]})

            result = api.grafana.import_dashboard(
                dashboard=dashboard_config, org_id=org_id, inputs=inputs, folderId=folder_id
            )
            if result["result"] or result["code"] == 412:
                return True
            else:
                raise ImportError(result)

        except Exception as err:
            logger.exception("组织({})创建默认仪表盘{}失败: {}".format(org_id, json_name, err))

        return False
