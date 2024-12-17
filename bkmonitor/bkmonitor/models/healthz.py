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


from django.db import models
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.utils.model_manager import Model


class HealthzTopoNode(Model):
    """
    节点关系前端维护
    """

    node_name = models.CharField(max_length=32, primary_key=True, verbose_name="节点名称")
    node_description = models.CharField(max_length=256, verbose_name="节点描述")

    class Meta:
        db_table = "healthz_topo_node"


class HealthzMetricRecord(Model):
    metric_alias = models.CharField(max_length=128, verbose_name="指标别名")
    result = models.TextField(verbose_name="采集结果")
    last_update = models.DateTimeField(verbose_name="最后更新")
    server_ip = models.GenericIPAddressField(verbose_name="服务器ip")

    class Meta:
        db_table = "healthz_metric_record"
        index_together = ["server_ip", "metric_alias"]


class HealthzMetricConfig(Model):
    CATEGORY_CHOICES = (
        ("redis", "Redis"),
        ("kafka", "Kafka"),
        ("beanstalk", "Beanstalk"),
        ("mysql", "Mysql"),
        ("consul", "Consul"),
        ("rabbitmq", "RabbitMQ"),
        ("celery", "Celery"),
        ("system", "System"),
        ("supervisor", "Supervisor"),
        ("gse_data", "Gse_Data"),
        ("pre_kafka", "Pre_kafka"),
        ("etl", "Etl"),
        ("post_kafka", "Post_kafka"),
        ("shipper", "Shipper"),
        ("tsdb_proxy", "Tsdb_proxy"),
        ("influxdb", "Influxdb"),
        ("graph_exporter", "Graph_exporter"),
    )
    COLLECT_TYPE_CHOICES = (
        ("saas", "saas"),
        ("backend", _lazy("后台")),
    )

    node_name = models.CharField(max_length=32, verbose_name="节点名称")
    description = models.CharField(max_length=1024, verbose_name="指标描述")
    category = models.CharField(max_length=32, verbose_name="指标分类", choices=CATEGORY_CHOICES)
    collect_metric = models.CharField(max_length=128, verbose_name="采集指标")
    collect_args = models.TextField(verbose_name="采集参数")
    collect_type = models.TextField(verbose_name="采集类型", choices=COLLECT_TYPE_CHOICES)

    collect_interval = models.IntegerField(verbose_name="采集周期", default=60)

    metric_alias = models.CharField(max_length=128, verbose_name="指标别名", unique=True)
    solution = models.TextField(verbose_name="解决方案", default="")

    class Meta:
        db_table = "healthz_metric_config"
