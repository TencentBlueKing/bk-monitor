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

from typing import Dict, List

from django.core.management.base import BaseCommand

from metadata.models.influxdb_cluster import InfluxDBClusterInfo
from metadata.models.storage import ClusterInfo, InfluxDBProxyStorage, InfluxDBStorage
from metadata.task.config_refresh import refresh_influxdb_route


class Command(BaseCommand):
    DEFAULT_DURATION_TIME = "30d"

    def handle(self, *args, **options):
        database = options.get("database")
        metric_content_path = options.get("metric_content_path")
        influxdb_proxy_cluster_id = options.get("influxdb_proxy_cluster_id")
        influxdb_cluster_names = options.get("influxdb_cluster_names")
        if not (metric_content_path and influxdb_proxy_cluster_id and influxdb_cluster_names):
            raise Exception("参数[metric_content_path, influxdb_proxy_cluster_id, influxdb_cluster_names]不能为空")
        influxdb_cluster_name_list = influxdb_cluster_names.split(",")
        if len(influxdb_cluster_name_list) != len(set(influxdb_cluster_name_list)):
            raise Exception("参数[influxdb_cluster_names]出现重复数值")
        # 检查存在
        if not self._check_exist(influxdb_proxy_cluster_id, influxdb_cluster_name_list):
            raise Exception("请确认influxdb proxy 集群和influxdb集群存在!")
        # 获取到 proxy storage id
        proxy_storage_map = self._get_proxy_storage_id(influxdb_proxy_cluster_id, influxdb_cluster_name_list)
        # 获取指标列表
        metric_list = self._refine_metric_list(metric_content_path)
        # 拆分实例集群及 metric 列表，以便于写入不同的实例
        cluster_metric_list_map = self._get_cluster_and_metric_list(influxdb_cluster_name_list, metric_list)
        # 采用 `update_or_create` 写入记录
        try:
            for influxdb_cluster_name, metric_list in cluster_metric_list_map.items():
                for m in metric_list:
                    proxy_storage_id = proxy_storage_map.get((influxdb_proxy_cluster_id, influxdb_cluster_name))
                    if proxy_storage_id is None:
                        self.stdout.write(
                            "not found proxy storage id by proxy_cluster_id: {}, instance_cluster: {}".format(
                                influxdb_proxy_cluster_id, influxdb_cluster_name
                            )
                        )
                        continue
                    InfluxDBStorage.objects.update_or_create(
                        real_table_name=m,
                        database=database,
                        defaults={
                            "table_id": f"{database}.{m}",
                            "storage_cluster_id": influxdb_proxy_cluster_id,
                            "source_duration_time": self.DEFAULT_DURATION_TIME,
                            "proxy_cluster_name": influxdb_cluster_name,
                            "influxdb_proxy_storage_id": proxy_storage_id,
                        },
                    )
        except Exception as e:
            raise Exception("写入 influxdb 信息失败，%s", e)
        # 写入 consul
        refresh_influxdb_route()
        self.stdout.write("写入数据成功!")

    def add_arguments(self, parser):
        # database 名称，用以组装结果表
        parser.add_argument("--database", type=str, default="10_bkmonitor_time_series_1573542", help="influxdb名称")
        # 指标文件所在的绝对路径
        parser.add_argument("--metric_content_path", type=str, help="指标所在文件的绝对路径")
        # influxdb proxy 集群ID
        parser.add_argument("--influxdb_proxy_cluster_id", type=int, help="influxdb proxy 集群 ID")
        # influxdb 集群名称
        parser.add_argument("--influxdb_cluster_names", type=str, help="influxdb 集群名称，多个以半角逗号分隔")

    def _check_exist(self, influxdb_proxy_cluster_id: int, influxdb_cluster_name_list: List[str]) -> bool:
        """检测 influxdb 实例集群及 proxy 集群是否存在"""
        if not ClusterInfo.objects.filter(cluster_id=influxdb_proxy_cluster_id).exists():
            return False
        if not InfluxDBClusterInfo.objects.filter(cluster_name__in=influxdb_cluster_name_list).exists():
            return False
        return True

    def _get_proxy_storage_id(self, influxdb_proxy_cluster_id: int, influxdb_cluster_name_list: List) -> Dict:
        qs = InfluxDBProxyStorage.objects.filter(
            proxy_cluster_id=influxdb_proxy_cluster_id, instance_cluster_name__in=influxdb_cluster_name_list
        )
        return {(obj.proxy_cluster_id, obj.instance_cluster_name): obj.id for obj in qs}

    def _refine_metric_list(self, path: str) -> List[str]:
        with open(path) as f:
            metric_content = f.read()
        # 以`\n` 拆分为单个数据
        return metric_content.split("\n")

    def _get_cluster_and_metric_list(self, influxdb_cluster_name_list: List, metric_list: List) -> Dict:
        # 以指标数量除以集群的数量向上取整为步长，拆分指标数组
        cluster_num = len(influxdb_cluster_name_list)
        metric_num = len(metric_list)
        if cluster_num > metric_num:
            raise Exception("指标数量小于集群数量，建议直接操作 admin")
        # 集群数量为1时，直接返回
        if cluster_num == 1:
            return {influxdb_cluster_name_list[0]: metric_list}
        # 如果可以整除，则按照商为步长分拆取值, 其它按照余数处理
        # 获取余数和商
        remainder = metric_num % cluster_num
        quotient = metric_num // cluster_num
        # metric 数量减去剩余为
        metric_num_for_range = metric_num - remainder
        cluster_metric_list_map = {}
        splitted_metric_list = []

        # 处理可以平分的数据
        for s in range(0, metric_num_for_range, quotient):
            splitted_metric_list.append(metric_list[s : s + quotient])

        # 组装数据，格式为{cluster_name: metric}
        for i, v in enumerate(splitted_metric_list):
            cluster_metric_list_map[influxdb_cluster_name_list[i]] = v
        # 处理剩余的数据
        for i, v in enumerate(metric_list[metric_num_for_range:]):
            cluster_metric_list_map[influxdb_cluster_name_list[i]].append(v)

        return cluster_metric_list_map
