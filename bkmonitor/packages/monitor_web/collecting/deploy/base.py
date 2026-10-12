"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
from dataclasses import dataclass
from typing import Any

from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion


@dataclass(frozen=True)
class CollectionStatistics:
    """采集实例统计。缺失结果不返回，不能当作零实例成功。"""

    total: int = 0
    failed: int = 0
    pending: int = 0
    running: int = 0


class BaseInstaller(abc.ABC):
    """
    安装器基类

    TODO: 所有操作加锁，并且加入异步回调状态更新
    """

    def __init__(self, collect_config: CollectConfigMeta, *args, **kwargs):
        self.collect_config = collect_config
        self.plugin = collect_config.plugin

    @classmethod
    @abc.abstractmethod
    def statistics(cls, configs: list[CollectConfigMeta]) -> dict[int, CollectionStatistics]:
        """批量查询统计，以监控采集配置 ID 为键；缺失或失败的结果不返回。"""

    @abc.abstractmethod
    def is_task_ready(self) -> bool:
        """查询当前部署版本的任务是否完成初始化，不表示部署成功。"""

    @abc.abstractmethod
    def install(self, install_config: dict, operation: str | None) -> dict:
        """
        部署
        :return: dict
        {
            "id": 1, # 采集配置ID
            "deployment_id": 1, # 采集部署配置ID
            "can_rollback": False, # 是否可以回滚
            "diff_node": {
                "is_modified": False,
                "added": [],
                "removed": []
                "unchanged": []
                "updated": []
            }
        }
        """
        return {}

    @abc.abstractmethod
    def upgrade(self, params: dict) -> dict:
        """
        升级
        :return: dict
        {
            "id": 1,
            "deployment_id": 1,
            "can_rollback": False,
            "diff_node": {
                "is_modified": False,
                "added": [],
                "removed": []
                "unchanged": []
                "updated": []
            }
        }
        """

    @abc.abstractmethod
    def uninstall(self):
        """
        卸载
        """

    @abc.abstractmethod
    def rollback(self, deployment_config_version: int | DeploymentConfigVersion | None = None):
        """
        回滚到某个版本，默认回滚到上一个版本
        :return: dict
        {
            "id": 1, # 采集配置ID
            "deployment_id": 1, # 采集部署配置ID
            "diff_node": {
                "is_modified": False,
                "added": [],
                "removed": []
                "unchanged": []
                "updated": []
            }
        }
        """

    @abc.abstractmethod
    def stop(self):
        """
        停止
        """

    @abc.abstractmethod
    def start(self):
        """
        启动
        """

    @abc.abstractmethod
    def run(self, action: str = None, scope: dict[str, Any] = None):
        """
        主动执行
        """

    @abc.abstractmethod
    def retry(self, instance_ids: list[str] = None):
        """
        重试实例
        """

    @abc.abstractmethod
    def revoke(self, instance_ids: list[int] = None):
        """
        终止实例
        """

    @abc.abstractmethod
    def status(self, *args, **kwargs):
        """
        实例状态
        """

    @abc.abstractmethod
    def instance_status(self, instance_id: str):
        """
        单个实例状态
        """
