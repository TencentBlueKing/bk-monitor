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
import json
from typing import List

from django.core.management.base import BaseCommand

from metadata.service.influxdb_instance import InfluxDBInstanceCluster


class Command(BaseCommand):
    def handle(self, *args, **options):
        cluster_name = options.get("influxdb_cluster_name")
        if not cluster_name:
            raise Exception("参数[influxdb_cluster_name]不能为空")
        hosts_path = options.get("influxdb_hosts_path")
        hosts = options.get("influxdb_hosts")
        if not (hosts_path or hosts):
            raise Exception("参数[influxdb_hosts_path和influxdb_hosts]不能同时为空")
        # 解析到host信息
        hosts = self.refine_hosts(hosts_path, hosts)
        # 插入数据
        InfluxDBInstanceCluster(cluster_name, hosts, options["is_readable"]).add()
        self.stdout.write("Influxdb实例集群插入成功!")

    def add_arguments(self, parser):
        # influxdb 集群
        parser.add_argument("--influxdb_cluster_name", type=str, help="influxdb 实例集群名称")
        # 主机名称，存储路径和终端输入值不能同时为空，如果都有值，则以文件中为准
        # 存储格式如下，其中 is_disabled、username、password、description可以不填写
        # is_disabled默认为false， username、password、description 为空
        """
        [
            {
                "host_name": "TEST1",
                "domain": "test.host",
                "port": 8086,
                "is_disabled": false,
                "username": "",
                "password": "",
                "description": ""
            }
        ]
        """
        parser.add_argument("--influxdb_hosts_path", type=str, help="influxdb 实例集群的主机信息的绝对地址")
        parser.add_argument("--influxdb_hosts", type=json.loads, help="influxdb 实例集群的主机信息，注意为json格式化")
        parser.add_argument("--is_readable", type=bool, default=True, help="是否可读")

    def refine_hosts(self, hosts_path: str, hosts: List) -> List:
        """获取主机信息"""
        if hosts_path:
            with open(hosts_path) as f:
                content = f.read()
            return json.loads(content)
        return hosts
