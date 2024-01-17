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
from typing import Dict, List

from django.core.management import BaseCommand, CommandError

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.vm.constants import VM_RETENTION_TIME, TimestampLen
from metadata.models.vm.utils import (
    access_vm_by_kafka,
    get_bkbase_data_name_and_topic,
    get_timestamp_len,
    get_vm_cluster_id_name,
    refine_bkdata_kafka_info,
)


class Command(BaseCommand):
    help = "接入计算平台 VM"

    def add_arguments(self, parser):
        parser.add_argument("--space_type", type=str, required=True, help="space_type")
        parser.add_argument("--space_id", type=str, required=True, help="space_id")
        parser.add_argument("--table_ids", type=str, required=False, help="table_id, split by ';'")
        parser.add_argument("--partition", type=int, required=False, default=1, help="接入时指定 partition 数量")
        parser.add_argument("--vm_cluster_name", type=str, required=False, default="", help="要接入到的 vm 集群名称")
        parser.add_argument(
            "--vm_retention_time", type=str, required=False, default=VM_RETENTION_TIME, help="vm 集群数据保留时间"
        )

    def handle(self, *args, **options):
        self._valid(options)
        # 获取参数
        space_type = options.get("space_type")
        space_id = options.get("space_id")
        kafka_storage_cluster_id = refine_bkdata_kafka_info()["cluster_id"]
        partition = options.get("partition")
        input_table_ids = options.get("table_ids") or ""
        input_table_id_list = input_table_ids.split(";") if input_table_ids else []

        # 获取空间下的结果表和数据源关系, 针对 0 业务的需要单独处理
        if space_id == "0":
            table_ids = self._get_zero_space_table_id(input_table_id_list)
        else:
            table_ids = self._get_space_table_id(space_type, space_id, input_table_id_list)
        # 如果没有匹配到结果表，直接返回
        if not table_ids:
            self.stdout.write("not found table id from space")
            return

        table_id_list = list(table_ids.keys())

        vm_cluster = get_vm_cluster_id_name(space_type, space_id, options.get("vm_cluster_name"))
        vm_cluster_name = vm_cluster["cluster_name"]
        vm_retention_time = options.get("vm_retention_time")
        # 过滤已经存在kafka中的结果表
        exist_table_id_list = self._filter_exist_table(table_id_list)
        # 过滤已经接入 kafka 存储，但是没有接入 vm 的结果表
        access_kafka_not_vm = self._filter_access_kafka_not_vm(exist_table_id_list)
        if access_kafka_not_vm:
            self.stdout.write(f"table_id: {json.dumps(access_kafka_not_vm)} has already access storage kafka, not vm")

        # 过滤已经接入 vm 的结果表
        accessed_vm_table_id_list = self._filter_accessed_vm_table(table_id_list)
        # 排除掉已经接入的数据
        need_create_table_id_list = list(set(table_id_list) - set(accessed_vm_table_id_list))
        if not need_create_table_id_list:
            self.stdout.write("all table_id has already access vm")
            return
        # 获取 table id 对应的计算平台名称及topic
        vm_table_id_data_name_and_topic = self._get_bkbase_name_and_topic(need_create_table_id_list)
        # 标记失败的结果表
        failed_access_vm_table_id = []
        # 开始进行接入
        table_id_vm_info, tale_id_kafka_info = {}, {}
        for table_id, name_and_topic in vm_table_id_data_name_and_topic.items():
            self.stdout.write(f"table_id: {table_id} start to access bkbase vm")
            try:
                bkdata_id_vm_table_id = access_vm_by_kafka(
                    table_id,
                    name_and_topic["raw_data_name"],
                    vm_cluster_name,
                    table_ids.get(table_id, {}).get("timestamp_len", TimestampLen.MILLISECOND_LEN.value),
                )
            except Exception as e:
                failed_access_vm_table_id.append({"table_id": table_id, "err_msg": str(e)})
                continue
            if bkdata_id_vm_table_id.get("err_msg"):
                failed_access_vm_table_id.append({"table_id": table_id, "err_msg": bkdata_id_vm_table_id["err_msg"]})
                continue
            name_and_topic["kafka_storage_exist"] = bkdata_id_vm_table_id.get("kafka_storage_exist")
            # 单独记录，仅对成功写入 vm 的结果表做进一步处理
            table_id_vm_info[table_id] = bkdata_id_vm_table_id
            tale_id_kafka_info[table_id] = name_and_topic

        # 如果要创建的和失败的数量一样，则直接返回
        if len(failed_access_vm_table_id) == len(need_create_table_id_list):
            self.stderr.write(f"all table_id failed access vm, table_id: {failed_access_vm_table_id}")
            return

        # 开始创建 kafka 记录
        failed_create_kafka_table_id = self._create_kafka_storage(
            tale_id_kafka_info, kafka_storage_cluster_id, partition
        )
        if failed_create_kafka_table_id:
            self.stderr.write(f"table_id: {json.dumps(failed_create_kafka_table_id)} create kafka storage error")

        bulk_create_vm_data = []
        for table_id, info in table_id_vm_info.items():
            self.stdout.write(f"start create vm record for table_id:{table_id}...")
            bulk_create_vm_data.append(
                models.AccessVMRecord(
                    data_type=models.AccessVMRecord.ACCESS_VM,
                    bcs_cluster_id=table_ids.get(table_id, {}).get("bcs_cluster_id"),
                    result_table_id=table_id,
                    storage_cluster_id=kafka_storage_cluster_id,
                    vm_cluster_id=vm_cluster["cluster_id"],
                    bk_base_data_id=info["bk_data_id"],
                    vm_result_table_id=info["clean_rt_id"],
                )
            )
        # 批量创建
        models.AccessVMRecord.objects.bulk_create(bulk_create_vm_data)
        # 刷新 consul
        for _, data_id_and_time in table_ids.items():
            self._refresh_consul(data_id_and_time["bk_data_id"])
        # 刷新 redis
        self._refresh_redis(space_type, space_id, list(table_ids.keys()))

        # 创建空间对应的记录
        models.SpaceVMInfo.objects.get_or_create(
            space_type=space_type,
            space_id=space_id,
            vm_cluster_id=vm_cluster["cluster_id"],
            defaults={"vm_retention_time": vm_retention_time},
        )
        # 如果有失败记录，则输出
        if failed_access_vm_table_id or failed_create_kafka_table_id:
            msg = "failed access vm table_id: {};failed create kafka table_id:{}".format(
                failed_access_vm_table_id, failed_create_kafka_table_id
            )
            self.stderr.write(msg)
        else:
            self.stdout.write("access bk data successfully!")

    def _valid(self, options: Dict):
        """校验参数"""
        if not options.get("vm_retention_time"):
            raise CommandError("vm_retention_time is null")
        # partition 不能小于 1
        if options["partition"] < 1:
            raise CommandError("partition input error, it must gte 1, please check and retry")

    def _get_zero_space_table_id(self, input_table_id_list: List) -> Dict:
        """获取 0 空间下的结果表"""
        if not input_table_id_list:
            input_table_id_list = (
                models.ResultTable.objects.filter(bk_biz_id=0, default_storage="influxdb")
                .exclude(table_id__startswith="agentmetrix")
                .values_list("table_id", flat=True)
            )
        # 过数据源对应的结果表
        table_id_data_id = {
            ds_rt["table_id"]: ds_rt["bk_data_id"]
            for ds_rt in models.DataSourceResultTable.objects.filter(table_id__in=input_table_id_list).values(
                "table_id", "bk_data_id"
            )
        }
        k8s_metric_data = {
            obj["K8sMetricDataID"]: obj["cluster_id"]
            for obj in models.BCSClusterInfo.objects.filter(K8sMetricDataID__in=table_id_data_id.values()).values(
                "cluster_id", "K8sMetricDataID"
            )
        }
        k8s_custom_metric_data = {
            obj["CustomMetricDataID"]: obj["cluster_id"]
            for obj in models.BCSClusterInfo.objects.filter(CustomMetricDataID__in=table_id_data_id.values()).values(
                "cluster_id", "CustomMetricDataID"
            )
        }

        # 获取数据源对应的上报时间戳的长度
        ds_time_len = self._get_data_time_len(list(table_id_data_id.values()))

        return {
            table_id: {
                "bk_data_id": bk_data_id,
                "timestamp_len": ds_time_len[bk_data_id],
                "bcs_cluster_id": k8s_custom_metric_data.get(bk_data_id) or k8s_metric_data.get(bk_data_id),
            }
            for table_id, bk_data_id in table_id_data_id.items()
        }

    def _get_space_table_id(self, space_type: str, space_id: str, input_table_id_list: List) -> Dict:
        """获取空间下的结果表"""
        all_data_id_list = (
            models.SpaceDataSource.objects.filter(space_id=space_id, space_type_id=space_type)
            .values_list("bk_data_id", flat=True)
            .distinct()
        )
        k8s_metric_data = {
            obj["K8sMetricDataID"]: obj["cluster_id"]
            for obj in models.BCSClusterInfo.objects.filter(K8sMetricDataID__in=all_data_id_list).values(
                "cluster_id", "K8sMetricDataID"
            )
        }
        k8s_custom_metric_data = {
            obj["CustomMetricDataID"]: obj["cluster_id"]
            for obj in models.BCSClusterInfo.objects.filter(CustomMetricDataID__in=all_data_id_list).values(
                "cluster_id", "CustomMetricDataID"
            )
        }
        # 过数据源对应的结果表
        table_id_data_id = {
            ds_rt["table_id"]: ds_rt["bk_data_id"]
            for ds_rt in models.DataSourceResultTable.objects.filter(bk_data_id__in=all_data_id_list).values(
                "table_id", "bk_data_id"
            )
        }
        # 获取写入 influxdb 的结果表
        table_id_list = models.ResultTable.objects.filter(
            table_id__in=table_id_data_id.keys(), default_storage="influxdb"
        ).values_list("table_id", flat=True)

        if input_table_id_list:
            table_id_list = table_id_list.filter(table_id__in=input_table_id_list)

        # 获取数据源对应的上报时间戳的长度
        ds_time_len = self._get_data_time_len(list(table_id_data_id.values()))

        return {
            table_id: {
                "bk_data_id": bk_data_id,
                "timestamp_len": ds_time_len[bk_data_id],
                "bcs_cluster_id": k8s_custom_metric_data.get(bk_data_id) or k8s_metric_data.get(bk_data_id),
            }
            for table_id, bk_data_id in table_id_data_id.items()
            if table_id in table_id_list
        }

    def _get_data_time_len(self, bk_data_id_list: list) -> Dict:
        """获取数据源的长度"""
        ret_data = {}
        for ds in models.DataSource.objects.filter(bk_data_id__in=bk_data_id_list).values("bk_data_id", "etl_config"):
            ret_data[ds["bk_data_id"]] = get_timestamp_len(data_id=ds["bk_data_id"], etl_config=ds["etl_config"])
        return ret_data

    def _get_bkbase_name_and_topic(self, table_id_list: List) -> Dict:
        """获取结果表对应的计算平台名称及需要的topic"""
        name_and_topic = {}
        for table_id in table_id_list:
            data_name_and_topic = get_bkbase_data_name_and_topic(table_id)
            name_and_topic[table_id] = {
                "raw_data_name": data_name_and_topic["data_name"],
                "topic": data_name_and_topic["topic_name"],
            }
        return name_and_topic

    def _filter_exist_table(self, table_id_list: List) -> List:
        """过滤已经存在的记录"""
        return list(models.KafkaStorage.objects.filter(table_id__in=table_id_list).values_list("table_id", flat=True))

    def _filter_accessed_vm_table(self, table_id_list: List) -> List:
        """过滤已经接入到 vm 的结果表"""
        return list(
            models.AccessVMRecord.objects.filter(result_table_id__in=table_id_list).values_list(
                "result_table_id", flat=True
            )
        )

    def _filter_access_kafka_not_vm(self, kafka_table_id_list: List) -> List:
        """过滤接入了 kafka 存储，但是没有接 vm 的结果表"""
        access_vm_table_ids = models.AccessVMRecord.objects.filter(result_table_id__in=kafka_table_id_list).values_list(
            "result_table_id", flat=True
        )
        return list(set(kafka_table_id_list) - set(access_vm_table_ids))

    def _create_kafka_storage(self, tale_id_kafka_info: Dict, storage_cluster_id: int, partition: int) -> List:
        """接入计算平台"""
        failed_table_id_list = []
        # 没有创建的结果表，需要创建
        for table_id, name_and_topic in tale_id_kafka_info.items():
            if name_and_topic["kafka_storage_exist"]:
                continue
            # 如果不存在，需要依次创建记录
            try:
                models.KafkaStorage.create_table(
                    table_id=table_id,
                    is_sync_db=True,
                    storage_cluster_id=storage_cluster_id,
                    topic=name_and_topic["topic"],
                    partition=partition,
                    use_default_format=False,
                )
            except Exception as e:
                msg = """
                the KafkaStorage is create failed, table_id={}, storage_cluster_id={}, topic={}, partition={}, err={}
                """.format(
                    table_id, storage_cluster_id, name_and_topic["topic"], partition, e
                )
                self.stderr.write(msg)
                failed_table_id_list.append(table_id)
                continue

        return failed_table_id_list

    def _refresh_consul(self, data_id: int):
        """刷新 consul 配置"""
        # 刷新 consul 配置
        self.stdout.write(f"start refresh consul config for data_id: {data_id}")
        models.DataSource.objects.get(bk_data_id=data_id).refresh_consul_config()
        self.stdout.write("refresh consul config success")

    def _refresh_redis(self, space_type: str, space_id: str, table_id_list: List[str]):
        """刷新 redis 配置"""
        self.stdout.write("start refresh router redis config")

        # 推送数据
        client = SpaceTableIDRedis()
        client.push_space_table_ids(space_type, space_id, is_publish=True)
        client.push_data_label_table_ids(table_id_list=table_id_list)
        client.push_table_id_detail(table_id_list=table_id_list)

        self.stdout.write("refresh router redis config success")
