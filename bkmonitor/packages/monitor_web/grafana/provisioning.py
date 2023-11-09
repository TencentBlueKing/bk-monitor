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
import json
import logging
import os
import typing
from dataclasses import asdict, dataclass
from typing import List

from blueapps.conf import settings
from django.core.cache import cache

from apm_ebpf.constants import DeepflowComp
from apm_ebpf.handlers.deepflow import DeepflowHandler
from bk_dataview.provisioning import Datasource, SimpleProvisioning, sync_data_sources
from bkmonitor.commons.tools import is_ipv6_biz
from core.drf_resource import api
from monitor_web.grafana.utils import patch_home_panels

logger = logging.getLogger(__name__)


@dataclass
class _DashboardInstance:
    dashboard: typing.Dict
    org_id: str
    inputs: typing.List
    folderId: int


class ApmEbpfDatasourceProvisioning:
    """
    APM EBPF数据源
    """

    _DATASOURCE_CACHE_KEY = "datasource:{org_name}"
    _DATASOURCE_CACHE_EXPIRE = 300

    # 仪表盘存放目录
    _FOLDER_NAME = "eBPF"

    @classmethod
    def datasources(cls, org_name: str, *_) -> List[Datasource]:
        key = cls._DATASOURCE_CACHE_KEY.format(org_name=org_name)
        res = cache.get(key)
        if res:
            return res

        res = []
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

        cache.set(key, res, cls._DATASOURCE_CACHE_EXPIRE)
        return res

    @classmethod
    def is_deepflow_template(cls, content):
        """
        判断是否是grafana-deepflow模版
        """
        for input_field in content.get("__inputs", []):
            if (
                input_field["type"] == "datasource"
                and input_field["pluginId"] == DeepflowComp.GRAFANA_DATASOURCE_TYPE_NAME
            ):
                return True

        return False

    @classmethod
    def generate_default_dashboards(
        cls, datasources, org_id, _1, _2, template, folder_id
    ) -> typing.List[_DashboardInstance]:
        type_mapping = {
            # 可能会存在多个相同的DeepFlow数据源导致Key相互覆盖 但是这里我们只需要任意取其中一个即可
            d["type"]: {"type": "datasource", "pluginId": d["type"], "value": d.get("uid", "")}
            for d in datasources
        }

        inputs = []
        for input_field in template.get("__inputs", []):
            if input_field["type"] != "datasource" or input_field["pluginId"] not in type_mapping:
                continue
            inputs.append({"name": input_field["name"], **type_mapping[input_field["pluginId"]]})

        folders = api.grafana.search_folder_or_dashboard(org_id=org_id, type="dash-folder")
        folder_mapping = {i["title"]: i for i in folders["data"]}

        if folder_id == 0:
            if cls._FOLDER_NAME not in folder_mapping:
                folder_id = api.grafana.create_folder(org_id=org_id, title=cls._FOLDER_NAME)["data"]["id"]
            else:
                folder_id = folder_mapping[cls._FOLDER_NAME]["id"]

        return [
            _DashboardInstance(
                dashboard=template,
                org_id=org_id,
                inputs=inputs,
                folderId=folder_id,
            )
        ]

    @classmethod
    def get_dashboard_mapping(cls, _):
        """
        获取此业务下所有的默认仪表盘
        """
        res = {}

        # 获取所有以apm-ebpf开头的仪表盘模版
        path = os.path.join(settings.BASE_DIR, f"packages/monitor_web/grafana/dashboards")
        templates = [n for n in os.listdir(path) if fnmatch.fnmatch(n, "apm-ebpf-*.json")]

        for template in templates:
            origin_name, _ = os.path.splitext(template)
            res[origin_name] = origin_name

        return res


class BkMonitorProvisioning(SimpleProvisioning):
    def datasources(self, request, org_name: str, org_id: int) -> List[Datasource]:
        res = list(super(BkMonitorProvisioning, self).datasources(request, org_name, org_id))

        # 增加EBPF数据源
        res.extend(ApmEbpfDatasourceProvisioning.datasources(org_name, org_id))

        return res

    def dashboards(self, request, org_name: str, org_id: int):
        """
        只执行一次
        """

        dashboard_mapping = {}
        dashboard_mapping.update(self.get_dashboard_mapping(org_name))
        # 接入APM EBPF仪表盘
        dashboard_mapping.update(ApmEbpfDatasourceProvisioning.get_dashboard_mapping(org_name))

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
        for i in not_created:
            if cls.create_default_dashboard(org_id, org_name, f"{dashboard_mapping[i]}.json"):
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

    @staticmethod
    def create_default_dashboard(org_id, org_name, json_name="host.json", folder_id=0, bk_biz_id=None):
        """
        创建仪表盘，并且设置为组织默认仪表盘
        :param org_id: 组织ID
        :param org_name: 组织名称
        :type org_id: int
        :param json_name: 配置文件名
        :type json_name: string
        :param folder_id: 目录 id
        :param bk_biz_id: 业务 id ==> org_name
        """
        datasources = api.grafana.get_all_data_source(org_id=org_id)["data"]
        if not datasources:
            org_name = str(bk_biz_id)
            provisioning = SimpleProvisioning()
            ds_list = []
            for ds in provisioning.datasources(None, org_name, org_id):
                if not isinstance(ds, Datasource):
                    raise ValueError("{} is not instance {}".format(type(ds), Datasource))
                ds_list.append(ds)
            sync_data_sources(org_id, ds_list)
            datasources = api.grafana.get_all_data_source(org_id=org_id)["data"]

        path = os.path.join(settings.BASE_DIR, f"packages/monitor_web/grafana/dashboards/{json_name}")
        try:
            errors = []

            with open(path, encoding="utf-8") as f:
                dashboard_config = json.loads(f.read())

            if ApmEbpfDatasourceProvisioning.is_deepflow_template(dashboard_config):
                # Step1: 判断是否为deepflow仪表盘文件 -> 执行多仪表盘创建逻辑
                dashboards = ApmEbpfDatasourceProvisioning.generate_default_dashboards(
                    datasources, org_id, org_name, json_name, dashboard_config, folder_id
                )
            else:
                # Step2: 默认逻辑: 创建单仪表盘
                dashboards = BkMonitorProvisioning.generate_default_dashboards(
                    datasources, org_id, org_name, json_name, dashboard_config, folder_id
                )

            for dashboard in dashboards:
                result = api.grafana.import_dashboard(**asdict(dashboard))

                if not result["result"]:
                    errors.append(f"组织({org_id})创建默认仪表盘({json_name})失败。接口返回：{result}")

            if errors:
                logger.exception(errors)
                return False

            return True
        except Exception as err:  # noqa
            logger.exception("组织({})创建默认仪表盘{}失败: {}".format(org_id, json_name, err))
            return False

    @staticmethod
    def generate_default_dashboards(
        datasources, org_id, _, json_name, template, folder_id
    ) -> typing.List[_DashboardInstance]:
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

        return [_DashboardInstance(dashboard=template, org_id=org_id, inputs=inputs, folderId=folder_id)]
