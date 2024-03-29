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
from datetime import datetime
from typing import Dict, List

from django.core.management.base import BaseCommand, CommandError

from metadata import models
from metadata.utils import consul_tools
from utils.redis_client import RedisClient


class Command(BaseCommand):
    ACTION_LIST = ["query", "delete"]

    def handle(self, *args, **options):
        """查询指标，并删除指定的指标信息

        目的是在用户更新指标后，从redis数据中移除时间窗口内不需要的指标
        """
        self._validate(options)

        if options["action"] == "query":
            self._query(options)
        else:
            self._delete(options)

    def add_arguments(self, parser):
        parser.add_argument("--action", type=str, help="action, query or delete")
        parser.add_argument("--data_id", type=int, help="data id, in order to filter metric")
        parser.add_argument(
            "--metrics", type=str, default=None, help="metric list, example: 'test1,test2,test3' separated by comma"
        )

    def _validate(self, options: Dict):
        """校验必须参数"""
        if options.get("action") not in self.ACTION_LIST:
            raise CommandError(f"action must be one of [{','.join(self.ACTION_LIST)}]")
        if not options.get("data_id"):
            raise CommandError("data_id is required")

    def _query(self, options: Dict):
        """查询现有的指标，确认到重复

        NOTE: 现阶段时间窗口为 30d，来源于 `TIME_SERIES_METRIC_EXPIRED_SECONDS`
        """
        qs = models.TimeSeriesGroup.objects.filter(bk_data_id=options["data_id"])
        if not qs.exists():
            raise ValueError(f"not found record by data_id: {options['data_id']}")
        obj = qs.first()
        # 从 redis 中获取指标和维度数据
        metric_dimensions = obj.get_metrics_from_redis()
        # 过滤到重复的指标和维度
        # NOTE: metric 内部应该不会出现重复情况
        metrics, dimensions = set(), set()
        for item in metric_dimensions:
            metrics.add(item["field_name"])
            dimensions = dimensions.union(set(item["tag_value_list"].keys()))
        # 返回数据
        repeated_metric_dimension_list = {
            "bk_data_id": obj.bk_data_id,
            "table_id": obj.table_id,
            "result_table_exist_field": {"repeated_field": []},
            "redis_exist_field": {"repeated_field": [], "repeated_detail": []},
        }
        # 判断指标是否重复维度
        repeated_metric_list = self._get_metric_dimensions(
            obj.table_id, metrics, models.ResultTableField.FIELD_TAG_DIMENSION
        )
        # 判断维度是否重复指标
        repeated_dimension_list = self._get_metric_dimensions(
            obj.table_id, dimensions, models.ResultTableField.FIELD_TAG_METRIC
        )
        rt_field_list = list(set(repeated_metric_list).union(repeated_dimension_list))
        repeated_metric_dimension_list["result_table_exist_field"]["repeated_field"] = rt_field_list

        # 取交集获取数据，如果存在，则输出指标和维度所在的数据
        intersection = metrics & dimensions

        # 查询重复的数据
        for metric in intersection:
            for item in metric_dimensions:
                if metric not in item["tag_value_list"]:
                    continue
                repeated_metric_dimension_list["redis_exist_field"]["repeated_detail"].append(item)
        repeated_metric_dimension_list["redis_exist_field"]["repeated_field"] = list(intersection)

        # 输出
        self.stdout.write(json.dumps(repeated_metric_dimension_list))

    def _get_metric_dimensions(self, table_id: str, field_name_list: List, tag: str) -> List:
        """通过 table id、指标或维度信息，返回已经存在的维度或指标"""
        field_list = models.ResultTableField.objects.filter(
            table_id=table_id, field_name__in=field_name_list, tag=tag
        ).values_list("field_name", flat=True)
        return field_list

    def _delete(self, options: Dict):
        """删除指定的指标"""
        metrics = options.get("metrics")
        if not metrics:
            raise ValueError("metrics is required")
        metric_list = metrics.split(",")
        data_id = options['data_id']
        # 删除记录中的指标
        obj = models.TimeSeriesGroup.objects.filter(bk_data_id=data_id).first()
        if not obj:
            self.stderr.write(f"data_id:{data_id} not found ts group")
            return
        models.TimeSeriesMetric.objects.filter(group_id=obj.time_series_group_id, field_name__in=metric_list).delete()
        # 删除结果表下对应的字段
        models.ResultTableField.objects.filter(table_id=obj.table_id, field_name__in=metric_list).delete()
        # 构建 client，然后删除指标
        client = RedisClient.from_envs(prefix="BK_MONITOR_TRANSFER")
        client.zrem(f"bkmonitor:metrics_{data_id}", *metric_list)

        # NOTE: 因为需要删除 transfer 内存中的指标记录，所以需要更新对应的 consul 数据
        ds = models.DataSource.objects.get(bk_data_id=data_id)
        self.stdout.write("start to push ds data to consul")
        hash_consul = consul_tools.HashConsul()

        # 刷新当前 data_id 的配置
        consul_data = ds.to_json(is_consul_config=True)
        consul_data["modify_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hash_consul.put(key=ds.consul_config_path, value=consul_data)
        self.stdout.write("push ds data to consul successfully")

        self.stdout.write(self.style.SUCCESS(f"metrics: [{metrics}] are removed"))
