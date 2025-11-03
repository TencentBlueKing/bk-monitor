"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import glob
import json
import logging
import os.path
from collections import defaultdict
from dataclasses import dataclass, fields

import yaml
from django.conf import settings

from core.drf_resource import api

from . import client
from .models import Dashboard as DashboardModel
from .models import DataSource
from .settings import grafana_settings
from .utils import os_env

logger = logging.getLogger(__name__)


@dataclass
class Datasource:
    """数据源标准格式"""

    name: str
    type: str
    url: str
    access: str = "direct"
    isDefault: bool = False
    withCredentials: bool = True
    database: None | str = None
    jsonData: None | dict = None
    version: int = 0


@dataclass
class Dashboard:
    """面板标准格式"""

    org_id: int
    dashboard: dict
    folderId: int
    inputs: list
    title: str = ""
    folder: str = ""
    overwrite: bool = True
    path: str = None
    pluginId: str = None


class BaseProvisioning:
    def datasources(self, request, org_name: str, org_id: int) -> list[Datasource]:
        raise NotImplementedError(".datasources() must be overridden.")

    def datasource_callback(
        self, request, org_name: str, org_id: int, datasource: Datasource, status: bool, content: str
    ):
        pass

    def dashboards(self, request, org_name: str, org_id: int) -> list[Dashboard]:
        raise NotImplementedError(".dashboards() must be overridden.")

    @classmethod
    def _generate_default_dashboards(cls, datasources, org_id, json_name, template, folder_id) -> list[Dashboard]:
        raise NotImplementedError("._generate_default_dashboards() must be overridden.")


class FileCache:
    def __init__(self):
        self.cache = {}


_FILE_CACHE = FileCache().cache


class SimpleProvisioning(BaseProvisioning):
    """简单注入"""

    file_suffix = ["yaml", "yml"]

    def read_conf(self, name, suffix):
        if not grafana_settings.PROVISIONING_PATH:
            return

        if f"{name}.{suffix}" in _FILE_CACHE:
            return _FILE_CACHE[f"{name}.{suffix}"]

        _FILE_CACHE[f"{name}.{suffix}"] = []
        paths = os.path.join(grafana_settings.PROVISIONING_PATH, name, f"*.{suffix}")
        for path in glob.glob(paths):
            with open(path, "rb") as fh:
                conf = fh.read()
                expand_conf = os.path.expandvars(conf)
                ds = yaml.load(expand_conf, Loader=yaml.FullLoader)
                _FILE_CACHE[f"{name}.{suffix}"].append(ds)
        return _FILE_CACHE[f"{name}.{suffix}"]

    def datasources(self, request, org_name: str, org_id: int) -> list[Datasource]:
        """不注入数据源"""
        with os_env(ORG_NAME=org_name, ORG_ID=org_id):
            for suffix in self.file_suffix:
                for conf in self.read_conf("datasources", suffix):
                    for ds in conf["datasources"]:
                        yield Datasource(**ds)

    def dashboards(self, request, org_name: str, org_id: int) -> list[Dashboard]:
        """固定目录下的json文件, 自动注入"""
        with os_env(ORG_NAME=org_name, ORG_ID=org_id):
            for suffix in self.file_suffix:
                for conf in self.read_conf("dashboards", suffix):
                    for p in conf["providers"]:
                        dashboard_path = os.path.expandvars(p["options"]["path"])
                        paths = os.path.join(dashboard_path, "*.json")
                        for path in glob.glob(paths):
                            with open(path, "rb") as fh:
                                dashboard = json.loads(fh.read())
                                title = dashboard.get("title")
                                if not title:
                                    continue
                                yield Dashboard(title=title, dashboard=dashboard)

    @classmethod
    def create_default_dashboard(cls, org_id, json_name, folder_id=0, bk_biz_id=None):
        """
        创建仪表盘，并且设置为组织默认仪表盘
        :param org_id: 组织ID
        :type org_id: int
        :param json_name: 配置文件名
        :type json_name: string
        :param folder_id: 目录 id
        :param bk_biz_id: 业务 id ==> org_name
        """
        datasources = api.grafana.get_all_data_source(org_id=org_id)["data"]
        if not datasources and bk_biz_id:
            org_name = str(bk_biz_id)
            provisioning = SimpleProvisioning()
            ds_list = []
            for ds in provisioning.datasources(None, org_name, org_id):
                if not isinstance(ds, Datasource):
                    raise ValueError(f"{type(ds)} is not instance {Datasource}")
                ds_list.append(ds)
            sync_data_sources(org_id, ds_list)
            datasources = api.grafana.get_all_data_source(org_id=org_id)["data"]

        if not datasources:
            logger.error(f"组织({org_id})创建默认仪表盘({json_name})失败: 未找到数据源")
            return False

        path = os.path.join(settings.BASE_DIR, f"packages/monitor_web/grafana/dashboards/{json_name}")
        try:
            errors = []

            with open(path, encoding="utf-8") as f:
                dashboard_config = json.loads(f.read())

            dashboards = cls._generate_default_dashboards(datasources, org_id, json_name, dashboard_config, folder_id)

            for dashboard in dashboards:
                params = {
                    "org_id": dashboard.org_id,
                    "dashboard": dashboard.dashboard,
                    "folderId": dashboard.folderId,
                    "inputs": dashboard.inputs,
                    "overwrite": dashboard.overwrite,
                }
                if dashboard.path and dashboard.pluginId:
                    params["path"] = dashboard.path
                    params["pluginId"] = dashboard.pluginId

                result = api.grafana.import_dashboard(**params)

                if not result["result"]:
                    errors.append(f"组织({org_id})创建默认仪表盘({json_name})失败。接口返回：{result}")

            if errors:
                logger.exception(errors)
                return False

            return True
        except Exception as err:  # noqa
            logger.exception(f"组织({org_id})创建默认仪表盘{json_name}失败: {err}")
            return False


def sync_data_sources(org_id: int, data_sources: list[Datasource]):
    """
    创建/更新数据源
    """
    logger.info(f"synchronize {len(data_sources)} datasources of org_id: {org_id}.")
    for ds in data_sources:
        instance = DataSource.objects.filter(org_id=org_id, name=ds.name).first()
        if not instance:
            client.create_datasource(org_id, ds)
            logger.info(f"org_id: {org_id} datasource: {ds.name} not exists, created.")
        else:
            if _is_datasource_change(instance, ds):
                client.update_datasource(org_id, instance.id, ds)
                logger.info(f"datasource: {ds.name}(id: {instance.id}) changed, updated.")
                continue
            logger.info(f"datasource: {ds.name}(id: {instance.id}) not updated, skipped.")


def _is_datasource_change(instance, dataclass_instance):
    """
    检查数据源是否有更新
    """
    ignore_fields = ["version"]
    for f in fields(dataclass_instance):
        if f.name in ignore_fields:
            # version字段为grafana自动补充 这里不进行校验
            continue
        instance_v = getattr(instance, _camel_to_snake(f.name))
        dataclass_instance_v = getattr(dataclass_instance, f.name)
        if not instance_v and not dataclass_instance_v:
            # 避免None和空字符串产生误判
            continue
        if isinstance(dataclass_instance_v, dict):
            # JSON格式在Datasource使用Text存储 所以这里进行转换
            dataclass_instance_v = json.dumps(dataclass_instance_v)
        if instance_v != dataclass_instance_v:
            return True

    return False


def _camel_to_snake(s):
    """将aaBBCc转换aa_b_b_cc格式"""
    result = []
    for c in s:
        if c.isupper():
            result.append("_")
            result.append(c.lower())
        else:
            result.append(c)
    return "".join(result)


_ORG_DASHBOARD_CACHE = defaultdict(set)


def sync_dashboards(org_id: int, dashboards: list[Dashboard]):
    """同步仪表盘"""

    if org_id not in _ORG_DASHBOARD_CACHE:
        exists_dashboards = set(
            DashboardModel.objects.filter(org_id=org_id, is_folder=False).values_list("title", flat=True)
        )
        _ORG_DASHBOARD_CACHE[org_id] = exists_dashboards

    for db in dashboards:
        if db.title in _ORG_DASHBOARD_CACHE[org_id]:
            continue

        client.update_dashboard(
            org_id,
            0,
            {
                "title": db.title,
                "dashboard": db.dashboard,
                "folder": db.folder,
                "folderUid": db.folderId,
                "overwrite": db.overwrite,
            },
        )
        _ORG_DASHBOARD_CACHE[org_id].add(db.title)


def group_by(iterators, get_key):
    res = {}
    for item in iterators:
        key = get_key(item)
        if not key:
            continue

        if key in res:
            res[key].append(item)
        else:
            res[key] = [item]

    return res
