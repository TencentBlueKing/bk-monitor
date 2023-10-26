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
from typing import Dict, List, Optional

from metadata import models

logger = logging.getLogger("metadata")


class InfluxDBInstanceCluster:
    def __init__(self, cluster_name: str, hosts: List[Dict], is_readable: Optional[bool] = True):
        self.cluster_name = cluster_name
        self.hosts = hosts
        self.is_readable = is_readable
        self.default_backup_rate_limit = 0

    def add(self):
        """添加记录"""
        self._add_hosts()
        self._add_cluster()

    def _add_hosts(self):
        """添加主机信息
        NOTE: 采用更新或创建的方式，可以重复执行
        """
        for h in self.hosts:
            models.InfluxDBHostInfo.objects.update_or_create(
                host_name=h["host_name"],
                defaults={
                    "domain_name": h["domain"],
                    "port": h["port"],
                    "username": h.get("username") or "",
                    "password": h.get("password") or "",
                    "description": h.get("description") or h["host_name"],
                    "status": h.get("is_disabled") or False,
                    "backup_rate_limit": h.get("backup_rate_limit") or self.default_backup_rate_limit,
                },
            )

    def _add_cluster(self):
        """添加集群信息"""
        for h in self.hosts:
            models.InfluxDBClusterInfo.objects.update_or_create(
                cluster_name=self.cluster_name,
                defaults={"host_name": h["host_name"], "host_readable": self.is_readable},
            )
