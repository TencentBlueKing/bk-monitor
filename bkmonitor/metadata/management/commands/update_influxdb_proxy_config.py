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

import yaml
from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from metadata import config
from metadata.models.influxdb_cluster import (
    InfluxDBClusterInfo,
    InfluxDBHostInfo,
    InfluxDBTagInfo,
)
from metadata.models.storage import InfluxDBStorage


class Command(BaseCommand):
    """
    根据配置文件，将influxdb-proxy相关的信息刷入mysql
    """

    def add_arguments(self, parser):
        parser.add_argument("-g", type=str, default="true", help="generate yaml")
        parser.add_argument("-t", type=str, nargs="*", default=[], help="type of generate yaml")
        parser.add_argument("-f", type=str, help="yaml file to change influxdb-proxy config")

    @atomic(config.DATABASE_CONNECTION_NAME)
    def handle(self, *args, **options):
        file_path = options.get("f")
        if not file_path:
            print("file_path should not be empty")
            return
        generate = options.get("g")
        # 如果传入generate，则生成配置文件
        if generate == "true":
            target_type = options.get("t")
            host_info = InfluxDBHostInfo.export_data()
            cluster_info = InfluxDBClusterInfo.export_data()
            route_info = InfluxDBStorage.export_data()
            tag_info = InfluxDBTagInfo.export_data()
            data = {
                "host_info": host_info,
                "cluster_info": cluster_info,
                "route_info": route_info,
                "tag_info": tag_info,
            }
            result = {}
            # 如果指定了类型，就只输出指定类型的数据
            if target_type:
                for target in target_type:
                    result[target] = data[target]
            else:
                result = data
            with open(file_path, mode="w+") as f:
                yaml.dump(result, f, default_flow_style=False)
            return
        # 否则从配置文件写入
        with open(file_path) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            host_info = data.get("host_info", None)
            if host_info is not None and isinstance(host_info, list):
                InfluxDBHostInfo.import_data(host_info)
            cluster_info = data.get("cluster_info", None)
            if cluster_info is not None and isinstance(cluster_info, list):
                InfluxDBClusterInfo.import_data(cluster_info)
            route_info = data.get("route_info", None)
            if route_info is not None and isinstance(route_info, list):
                InfluxDBStorage.import_data(route_info)
            tag_info = data.get("tag_info", None)
            if tag_info is not None and isinstance(tag_info, list):
                InfluxDBTagInfo.import_data(tag_info)
