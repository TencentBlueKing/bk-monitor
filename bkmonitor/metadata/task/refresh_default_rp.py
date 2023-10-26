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

from django.conf import settings

from metadata import models

logger = logging.getLogger("metadata")


def main():
    """批量刷新所有influxdb backend的默认RP策略"""

    for influxdb_host in models.InfluxDBHostInfo.objects.all():
        # 查询机器归属哪个influxdb集群
        clusters = [
            cluster["cluster_name"]
            for cluster in models.InfluxDBClusterInfo.objects.filter(host_name=influxdb_host.host_name).values(
                "cluster_name"
            )
        ]
        # 查询该集群下有哪些结果表是需要刷新配置的
        refresh_dbset = {
            storage["database"]
            for storage in models.InfluxDBStorage.objects.filter(
                proxy_cluster_name__in=clusters, use_default_rp=True, enable_refresh_rp=True
            ).values("database")
        }
        influxdb_host.update_default_rp(refresh_dbset)
        logger.info(
            "influxdb->[{}:{}] update default_rp->[{}] success.".format(
                influxdb_host.domain_name, influxdb_host.port, settings.TS_DATA_SAVED_DAYS
            )
        )
