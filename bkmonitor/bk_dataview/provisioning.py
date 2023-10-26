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
import glob
import json
import logging
import os.path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Union

import yaml

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
    database: Union[None, str] = None
    jsonData: Union[None, Dict] = None
    version: int = 0


@dataclass
class Dashboard:
    """面板标准格式"""

    title: str
    dashboard: Dict
    folder: str = ""
    folderUid: str = ""
    overwrite: bool = True


class BaseProvisioning:
    def datasources(self, request, org_name: str, org_id: int) -> List[Datasource]:
        raise NotImplementedError(".datasources() must be overridden.")

    def datasource_callback(
        self, request, org_name: str, org_id: int, datasource: Datasource, status: bool, content: str
    ):
        pass

    def dashboards(self, request, org_name: str, org_id: int) -> List[Dashboard]:
        raise NotImplementedError(".dashboards() must be overridden.")


_FILE_CACHE = {}


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
                yield ds

    def datasources(self, request, org_name: str, org_id: int) -> List[Datasource]:
        """不注入数据源"""
        with os_env(ORG_NAME=org_name, ORG_ID=org_id):
            for suffix in self.file_suffix:
                for conf in self.read_conf("datasources", suffix):
                    for ds in conf["datasources"]:
                        yield Datasource(**ds)

    def dashboards(self, request, org_name: str, org_id: int) -> List[Dashboard]:
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


_ORG_DATASOURCES_CACHE = defaultdict(set)


def sync_data_sources(org_id: int, data_sources: List[Datasource]):
    """同步数据源"""

    if org_id not in _ORG_DATASOURCES_CACHE:
        exists_data_sources = set(DataSource.objects.filter(org_id=org_id).values_list("name", flat=True))
        _ORG_DATASOURCES_CACHE[org_id] = exists_data_sources

    for ds in data_sources:
        if ds.name in _ORG_DATASOURCES_CACHE[org_id]:
            continue

        client.create_datasource(org_id, ds)
        _ORG_DATASOURCES_CACHE[org_id].add(ds.name)


_ORG_DASHBOARD_CACHE = defaultdict(set)


def sync_dashboards(org_id: int, dashboards: List[Dashboard]):
    """同步仪表盘"""

    if org_id not in _ORG_DASHBOARD_CACHE:
        exists_dashboards = set(
            DashboardModel.objects.filter(org_id=org_id, is_folder=False).values_list("title", flat=True)
        )
        _ORG_DASHBOARD_CACHE[org_id] = exists_dashboards

    for db in dashboards:
        if db.title in _ORG_DASHBOARD_CACHE[org_id]:
            continue

        client.update_dashboard(org_id, 0, db)
        _ORG_DASHBOARD_CACHE[org_id].add(db.title)
