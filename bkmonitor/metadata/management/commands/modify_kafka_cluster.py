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

from django.core.management.base import BaseCommand

from metadata.service.data_source import modify_kafka_cluster_id


class Command(BaseCommand):
    def handle(self, *args, **options):
        bk_data_id = options.get("bk_data_id")
        kafka_topic = options.get("kafka_topic")
        kafka_partition = options.get("kafka_partition")
        if not (bk_data_id or kafka_topic):
            raise Exception("参数[bk_data_id和kafka_topic]不能为空")

        # 变更操作
        modify_kafka_cluster_id(bk_data_id, kafka_topic, kafka_partition)
        self.stdout.write("变更kafka集群成功!")

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_id", type=int, default=None, help="数据源ID")
        parser.add_argument("--kafka_topic", type=str, default=None, help="kafka topic")
        parser.add_argument("--kafka_partition", type=str, default=None, help="kafka partition 数量")
