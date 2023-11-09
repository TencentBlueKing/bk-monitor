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
from dataclasses import dataclass, fields
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


def sync_data_sources(org_id: int, data_sources: List[Datasource]):
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
            result.append('_')
            result.append(c.lower())
        else:
            result.append(c)
    return ''.join(result)


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
