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
import logging
import typing

from blueapps.conf import settings

from bk_dataview.api import get_or_create_user, sync_user_role
from bk_dataview.provisioning import Dashboard, SimpleProvisioning
from bkmonitor.commons.tools import is_ipv6_biz
from monitor_web.grafana.utils import patch_home_panels

logger = logging.getLogger(__name__)


class BkMonitorProvisioning(SimpleProvisioning):
    def dashboards(self, request, org_name: str, org_id: int):
        """
        注册默认仪表盘
        @BkMonitorProvisioning返回空列表 不走外层sync_dashboards逻辑
        注册仪表盘操作在@method: self.upsert_dashboards里完成
        """

        dashboard_mapping = self.get_dashboard_mapping(org_name)

        self.upsert_dashboards(org_id, org_name, dashboard_mapping)

        yield from []

    @classmethod
    def upsert_dashboards(cls, org_id, org_name, dashboard_mapping):
        from monitor.models import ApplicationConfig

        dashboard_keys = set(dashboard_mapping.keys())
        created = set(
            ApplicationConfig.objects.filter(key__in=dashboard_keys, cc_biz_id=org_name, value="created").values_list(
                "key", flat=True
            )
        )
        not_created = dashboard_keys - created

        if not_created:
            # 确保admin用户存在
            user = get_or_create_user("admin")
            sync_user_role(org_id, user["id"], "Admin")

        for i in not_created:
            # 不存在则进行创建
            if cls.create_default_dashboard(org_id, f"{dashboard_mapping[i]}.json", bk_biz_id=org_name):
                ApplicationConfig.objects.get_or_create(cc_biz_id=org_name, key=i, value="created")

    @classmethod
    def get_dashboard_mapping(cls, org_name):
        """
        获取所有默认的仪表盘
        返回: Dict
                - Key: 此业务仪表盘唯一标识
                - Value: 仪表盘对应的Dashboard文件名称(不带.json后缀)
        """
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

        return grafana_default_dashboard_map

    @classmethod
    def _generate_default_dashboards(
        cls, datasources, org_id, json_name, template, folder_id
    ) -> typing.List[Dashboard]:
        data_sources = {
            data_source["type"]: {
                "type": "datasource",
                "pluginId": data_source["type"],
                "value": data_source.get("uid", ""),
            }
            for data_source in datasources
        }

        if json_name == "home.json":
            template["panels"] = patch_home_panels()
        inputs = []
        for input_field in template.get("__inputs", []):
            if input_field["type"] != "datasource" or input_field["pluginId"] not in data_sources:
                continue
            inputs.append({"name": input_field["name"], **data_sources[input_field["pluginId"]]})

        return [
            Dashboard(
                org_id=org_id,
                dashboard=template,
                inputs=inputs,
                folderId=folder_id,
            )
        ]
