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

from django.core.management.base import BaseCommand, CommandError

from metadata.models import ClusterInfo, DataSource, DataSourceResultTable, KafkaStorage


class Command(BaseCommand):
    help = "switch data source kafka cluster"

    def add_arguments(self, parser):
        parser.add_argument("--data_ids", type=int, nargs="*", help="switched data id")
        parser.add_argument("--bk_data_ids", type=str, help="switched data id, split by comma")
        # frontend or backend
        parser.add_argument(
            "--kind", type=str, help="switch frontend_kafka or backend_kafka,please type frontend or backend"
        )
        parser.add_argument("--kafka_cluster_id", type=int, help="kafka cluster id")

    def handle(self, *args, **options):
        self.stdout.write("start to switch kafka cluster")

        data_ids = options.get("data_ids")
        bk_data_ids = options.get("bk_data_ids")
        cluster_id = options.get("kafka_cluster_id")
        kind = options.get("kind")
        # 校验不能为空
        if not (data_ids or bk_data_ids):
            raise CommandError("one of --data_ids and --bk_data_ids option must be given")

        if not cluster_id:
            raise CommandError("option --kafka_cluster_id must be given")
        if not kind:
            raise CommandError("option --kind must be given")

        if bk_data_ids:
            data_ids = [int(data_id) for data_id in bk_data_ids.split(",")]

        # 校验数据
        if not ClusterInfo.objects.filter(cluster_id=cluster_id).exists():
            raise CommandError(f"kafka_cluster_id: {cluster_id} not found, please register into ClusterInfo")

        if kind == 'frontend':
            self.switch_frontend_kafka(data_ids=data_ids, new_cluster_id=cluster_id)
        elif kind == 'backend':
            self.switch_backend_kafka(data_ids=data_ids, new_cluster_id=cluster_id)
        else:
            raise CommandError("option --kind must be given")

        self.stdout.write(f"data_ids: {data_ids} has switch to kafka_cluster: {cluster_id}")

    def switch_frontend_kafka(self, data_ids, new_cluster_id):
        """
        变更前端Kafka（写往Transfer的Kafka）集群
        @param data_ids: 要变更的data_id列表
        @param new_cluster_id: 变更后的集群id
        """
        ds_objs = DataSource.objects.filter(bk_data_id__in=data_ids)
        diff_data_ids = set(data_ids) - set(ds_objs.values_list("bk_data_id", flat=True))
        if diff_data_ids:
            self.stdout.write(f"data_ids: {diff_data_ids} not found from datasource")

        # 更新数据
        self.stdout.write(f"data_ids: {data_ids}, kafka_cluster_id: {new_cluster_id} start to switch")
        ds_objs.update(mq_cluster_id=new_cluster_id)

        # 刷新配置
        for obj in ds_objs:
            obj.refresh_outer_config()

    def switch_backend_kafka(self, data_ids, new_cluster_id):
        """
        变更后端Kafka（Transfer写往VM等后端存储的分发Kafka）集群
        @param data_ids: 要变更的data_id列表
        @param new_cluster_id: 变更后的集群id
        """
        ds_objs = DataSource.objects.filter(bk_data_id__in=data_ids)
        diff_data_ids = set(data_ids) - set(ds_objs.values_list("bk_data_id", flat=True))
        if diff_data_ids:
            self.stdout.write(f"data_ids: {diff_data_ids} not found from datasource")
        # 过滤获取对应的table_ids
        table_ids = DataSourceResultTable.objects.filter(bk_data_id__in=data_ids).values_list("table_id", flat=True)
        # 获取KafkaStorage数据，并更新
        kafka_storage_objs = KafkaStorage.objects.filter(table_id__in=table_ids)
        kafka_storage_objs.update(storage_cluster_id=new_cluster_id)
        #  刷新配置
        for ds in ds_objs:
            ds.refresh_outer_config()
