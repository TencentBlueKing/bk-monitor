# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
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

from django.conf import settings

from apm_ebpf.models import DeepflowDashboardRecord
from bk_dataview.provisioning import Dashboard, Datasource, SimpleProvisioning
from core.drf_resource import api

logger = logging.getLogger(__name__)


class ApmEbpfProvisioning(SimpleProvisioning):
    """
    APM EBPF仪表盘创建
    此Provisioning没有注册在PROVISIONING_CLASSES中的原因是
    因为如果访问时才创建的话
    那么多个用户同时访问仪表盘页面时会出现并发问题导致仪表盘创建了(API无异常)但没有显示到页面的Bug
    所以实际创建逻辑在apm_ebpf定时任务后
    写在这里的原因是防止代码分散
    """

    _FOLDER_NAME = "eBPF"
    # eBPF的仪表盘模版插件Id 需要与apm_ebpf/*.json文件下__inputs.pluginId一致
    _TEMPLATE_PLUGIN_ID = "deepflowio-deepflow-datasource"

    @classmethod
    def convert_to_datasource(cls, datasources, _type):
        """
        将APM发现的有效数据源转换为Grafana处定义的数据源格式
        """

        res = []
        for datasource in datasources:
            res.append(
                Datasource(
                    name=datasource.name,
                    type=_type,
                    url="",
                    access="proxy",
                    withCredentials=False,
                    jsonData={"requestUrl": datasource.request_url, "traceUrl": datasource.tracing_url},
                )
            )

        return res

    @classmethod
    def get_dashboard_mapping(cls, _):
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
    def upsert_dashboards(cls, org_id, org_name, dashboard_mapping):
        dashboard_keys = set(dashboard_mapping.keys())

        created = set(
            DeepflowDashboardRecord.objects.filter(name__in=dashboard_keys, bk_biz_id=org_name).values_list(
                "name", flat=True
            )
        )

        not_created = dashboard_keys - created
        for i in not_created:
            # 不存在则进行创建
            if cls.create_default_dashboard(org_id, f"{dashboard_mapping[i]}.json", bk_biz_id=org_name):
                DeepflowDashboardRecord.objects.get_or_create(bk_biz_id=org_name, name=i)

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
