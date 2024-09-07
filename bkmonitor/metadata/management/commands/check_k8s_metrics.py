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
from django.core.management import BaseCommand

from bkmonitor.utils.k8s_metric import get_built_in_k8s_metrics
from metadata import models

# 这里添加需要更新的指标名
TARGET_METRIC_NAME_LIST = [] or """""".split("\n")

IGNORE_DIMENSIONS = ["bk_instance", "bk_job"]


class Command(BaseCommand):
    """
    打印配置文件中内置k8s指标与标准集群k8s指标的差异，输出需增加的指标信息（yaml格式） & 需删除指标名列表
    """

    def add_arguments(self, parser):
        """
        增加参数配置
        :param parser:
        :return:
        """

        parser.add_argument("cluster_id", type=str, help="standard cluster id")

    def handle(self, *args, **options):
        cluster_id = options.get("cluster_id")
        # 获取标准集群id参数，拉取k8s系统指标信息
        try:
            cluster = models.BCSClusterInfo.objects.get(cluster_id=cluster_id)
            ts_group_id = cluster.K8sMetricDataID
        except models.BCSClusterInfo.DoesNotExist:
            raise Exception("cluster {} doesn't exist!".format(cluster_id))

        try:
            ts_group = models.TimeSeriesGroup.objects.get(bk_data_id=ts_group_id)
            k8s_metrics = ts_group.get_metric_info_list_with_label("", "")
        except models.TimeSeriesGroup.DoesNotExist:
            raise Exception("cluster {} related ts group {} doesn't exist!".format(cluster_id, ts_group_id))
        # 读取配置文件中的内置k8s指标
        origin_k8s_metrics = get_built_in_k8s_metrics()
        metrics_map = {metric["field_name"]: metric for metric in origin_k8s_metrics}
        add_metrics = []

        for metric in k8s_metrics:
            metric = {
                "description": metric["description"],
                "field_name": metric["field_name"],
                "tag_list": [tag for tag in metric["tag_list"] if tag["field_name"] not in IGNORE_DIMENSIONS],
            }
            if TARGET_METRIC_NAME_LIST and metric["field_name"] not in TARGET_METRIC_NAME_LIST:
                continue
            if not metrics_map.get(metric["field_name"]):
                add_metrics.append(metric)
            else:
                metrics_map.pop(metric["field_name"])
        # 打印标准集群对比配置文件新增、删除的k8s系统指标
        if TARGET_METRIC_NAME_LIST:
            print("delete metrics field name:", list(metrics_map.keys()))

        print(
            "add metrics:",
            yaml.dump(
                add_metrics,
            ),
        )
        with open("add_metrics.yaml", "w") as f:
            yaml.dump(add_metrics, f)
