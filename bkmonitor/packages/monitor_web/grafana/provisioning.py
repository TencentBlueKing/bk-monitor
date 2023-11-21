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
import fnmatch
import logging
import os
import typing
from typing import List

from blueapps.conf import settings

from apm_ebpf.constants import DeepflowComp
from apm_ebpf.handlers.deepflow import DeepflowHandler
from bk_dataview.provisioning import Dashboard, Datasource, SimpleProvisioning
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.utils.cache import CacheType, using_cache
from core.drf_resource import api
from monitor_web.grafana.utils import patch_home_panels

logger = logging.getLogger(__name__)


class ApmEbpfProvisioning(SimpleProvisioning):
    _FOLDER_NAME = "eBPF"
    # eBPF的仪表盘模版插件Id 需要与apm_ebpf/*.json文件下__inputs.pluginId一致
    _TEMPLATE_PLUGIN_ID = "deepflowio-deepflow-datasource"

    @using_cache(CacheType.GRAFANA)
    def datasources(self, request, org_name: str, org_id: int) -> List[Datasource]:
        res = []
        # 增加EBPF数据源
        datasources = DeepflowHandler(org_name).list_datasources()

        for datasource in datasources:
            res.append(
                Datasource(
                    name=datasource.name,
                    type=DeepflowComp.GRAFANA_DATASOURCE_TYPE_NAME,
                    url="",
                    access="proxy",
                    withCredentials=False,
                    jsonData={"requestUrl": datasource.request_url, "traceUrl": datasource.tracing_url},
                )
            )

        return res

    def dashboards(self, request, org_name: str, org_id: int):
        """
        注册默认仪表盘
        @ApmEbpfProvisioning返回空列表 不走外层sync_dashboards逻辑
        注册仪表盘操作在@method: self.upsert_dashboards里完成
        """
        if not DeepflowHandler(org_name).list_datasources():
            yield from []

        # 接入APM EBPF仪表盘
        dashboard_mapping = self.get_dashboard_mapping(org_name)

        self.upsert_dashboards(org_id, org_name, dashboard_mapping)

        yield from []

    def get_dashboard_mapping(self, _):
        """
        获取此业务下所有的默认仪表盘
        """
        res = {}

        # 获取apm_ebpf目录下所有*.json文件
        directory = "apm_ebpf"
        path = os.path.join(settings.BASE_DIR, f"packages/monitor_web/grafana/dashboards/{directory}")
        templates = [n for n in os.listdir(path) if fnmatch.fnmatch(n, "*.json")]

        for template in templates:
            origin_name, _ = os.path.splitext(template)
            res[f"{directory}_{origin_name}"] = os.path.join(directory, origin_name)

        return res

    @classmethod
    def delete_empty_directory(cls):
        """删除空的eBPF目录"""
        orgs = api.grafana.get_all_organization()
        if not orgs.get("result"):
            logger.info(f"failed to get organization, result: {orgs}")
            return

        for org in orgs.get("data", []):
            folders = api.grafana.list_folder(org_id=org["id"])
            if not folders.get("result"):
                logger.warning(f"list folder of org_id: {org['id']} failed, result: {folders}, skipped")
                continue

            ebpf_folder = next((f for f in folders.get("data", []) if f["title"] == cls._FOLDER_NAME), None)
            if not ebpf_folder:
                continue

            dashboards = api.grafana.search_folder_or_dashboard(org_id=org["id"], folderIds=[ebpf_folder["id"]])
            if dashboards.get("result") and not dashboards.get("data"):
                api.grafana.delete_folder(org_id=org["id"], uid=ebpf_folder["id"])
                logger.info(f"delete {cls._FOLDER_NAME} folder of org_id: {org['id']}(org_name: {org['name']})")

    @classmethod
    def _generate_default_dashboards(
        cls, datasources, org_id, json_name, template, folder_id
    ) -> typing.List[Dashboard]:
        type_mapping = {
            # 可能会存在多个相同的DeepFlow数据源导致Key相互覆盖 但是这里我们只需要任意取其中一个即可 因为多个数据源可以共用一个仪表盘
            d["type"]: {"type": "datasource", "pluginId": d["type"], "value": d.get("uid", "")}
            for d in datasources
        }
        if cls._TEMPLATE_PLUGIN_ID not in type_mapping:
            # 此业务无eBPF集群 不创建仪表盘
            return []

        inputs = []
        for input_field in template.get("__inputs", []):
            if input_field["type"] != "datasource" or input_field["pluginId"] not in type_mapping:
                continue
            inputs.append({"name": input_field["name"], **type_mapping[input_field["pluginId"]]})

        folders = api.grafana.search_folder_or_dashboard(org_id=org_id, type="dash-folder")
        folder_mapping = {i["title"]: i for i in folders["data"]}

        if folder_id == 0:
            # 如果没有指定文件ID 则将仪表盘存放只eBPF目录下
            if cls._FOLDER_NAME not in folder_mapping:
                folder_id = api.grafana.create_folder(org_id=org_id, title=cls._FOLDER_NAME)["data"]["id"]
            else:
                folder_id = folder_mapping[cls._FOLDER_NAME]["id"]

        ds = Dashboard(
            org_id=org_id,
            dashboard=template,
            inputs=inputs,
            folderId=folder_id,
        )
        if template.get("__path"):
            # __path为eBPF模版中自定义字段 如果字段存在则证明为数据源内置仪表盘
            ds.pluginId = cls._TEMPLATE_PLUGIN_ID
            ds.path = template["__path"]

        return [ds]


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
