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

from django.core.management import BaseCommand

from metadata.models import DataSource, DataSourceResultTable, KafkaStorage


class Command(BaseCommand):
    """根据data_id 接入kafka"""

    help = "access bkdata prom compute datasource command"

    def add_arguments(self, parser):
        parser.add_argument("--data_id", type=str, required=True, help="data id")
        parser.add_argument("--storage_cluster_id", type=str, required=True, help="接入kafka所需的存储集群")
        parser.add_argument("--topic", type=str, required=False, help="接入时指定该数据源topic")
        parser.add_argument("--partition", type=int, required=False, default=1, help="接入时指定partition数量")

    def handle(self, *args, **options):
        # 获取BCS 集群ID
        data_id = options.get("data_id")
        storage_cluster_id = options.get("storage_cluster_id")
        topic = options.get("topic")
        partition = options.get("partition")

        if partition < 1:
            self.stderr.write("partition input error, it must gt 1, please check and retry")
            return

        if not storage_cluster_id:
            self.stderr.write("storage_cluster_id input error, it can't be empty, please check and retry")
            return

        self.stdout.write("start access kafka, data_id={}".format(data_id))

        table_id_list = DataSourceResultTable.objects.filter(bk_data_id=data_id).values_list("table_id", flat=True)

        self.stdout.write("find datasource result table, data_id={}, table_id_list={}".format(data_id, table_id_list))
        # 如果该data_id 没有对应的结果表，则退出
        if not table_id_list:
            self.stderr.write("the table list is empty, table_id_list={}".format(table_id_list))
            return

        kafka_storages = KafkaStorage.objects.filter(table_id__in=table_id_list).values("table_id", "topic")
        # 如果存在KafkaStorage。说明已经接入过kafka，直接打印结果，避免重复接入

        if kafka_storages and len(kafka_storages) == len(table_id_list):
            self.stdout.write("found kafka_storages, nums = {}".format(len(kafka_storages)))
            for kafka_storage in kafka_storages:
                self.stdout.write(
                    "table_id = {}, topic={}".format(kafka_storage.get("table_id"), kafka_storage.get("topic"))
                )
            return

        self.stdout.write("the kafka_storages is not exists, now create")
        ks_list = []
        for table_id in table_id_list:
            # 如果不存在，需要依次创建记录
            try:
                if topic:
                    ks = KafkaStorage.create_table(
                        table_id=table_id,
                        is_sync_db=True,
                        storage_cluster_id=storage_cluster_id,
                        topic=topic,
                        partition=partition,
                    )
                else:
                    ks = KafkaStorage.create_table(
                        table_id=table_id, is_sync_db=True, storage_cluster_id=storage_cluster_id, partition=partition
                    )
                self.stdout.write(
                    "the KafkaStorage is created, table_id={}, storage_cluster_id={},"
                    " topic={}".format(table_id, storage_cluster_id, ks.topic)
                )
                # 记录所有的kafkaStorage对象
                ks_list.append(ks)
            except Exception as e:
                msg = "the KafkaStorage is create failed, table_id={}, storage_cluster_id={}, err={}".format(
                    table_id, storage_cluster_id, e
                )
                self.stderr.write(msg)
                continue

        self.stdout.write("refresh kafka storage")
        # 刷洗kafka的配置
        for ks in ks_list:
            self.stdout.write("start refresh kafka storage, table_id={}, topic={}".format(ks.table_id, ks.topic))
            ks.ensure_topic()
            self.stdout.write("refresh kafka storage success, table_id={}, topic={}".format(ks.table_id, ks.topic))

        # 刷新consul配置
        self.stdout.write("start refresh consul config")
        DataSource.objects.get(bk_data_id=data_id).refresh_consul_config()
        self.stdout.write("refresh consul config success")

        self.stdout.write("access kafka successful")

        return
