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

from typing import Dict, List, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from metadata import models
from metadata.models.data_pipeline.constants import ETLConfig
from metadata.models.space import constants


class Command(BaseCommand):
    help = "init data pipeline"

    internal_data_ids = {
        ETLConfig.ALERT.value: [1000, 1100000],
        ETLConfig.METRIC.value: [
            1001,
            1002,
            1003,
            1004,
            1005,
            1006,
            1007,
            1013,
            1008,
            1009,
            1010,
            1011,
            1100001,
            1100002,
            1100003,
            1100004,
            1100005,
            1100006,
            1100007,
            1100009,
            1100010,
            1100011,
            1100012,
            1100014,
            1100015,
            1100016,
            1110000,
        ],
        ETLConfig.EVENT.value: [1100008],
    }
    name_prefix = "system_internal"

    def handle(self, *args, **options):
        """初始化操作

        issue:
        - 初始化的链路管道名称怎样命名
        - 一个数据源 ID 上报的数据，是否会流转到多个存储；如果存在，则数据源属于多个管道
        - trace 类型过滤是怎样的
        - 默认的管道的创建，是否允许区分不同场景或空间进行设置默认
        """
        # 获取数据
        data_id_name, data_id_etl_config, data_id_kafka, data_id_transfer = self._get_data_source()
        data_id_rt = self._get_data_id_rt()
        # 初始化 pipeline 数据
        data_id_pipeline = self._init_pipeline(data_id_kafka, data_id_transfer, data_id_rt)
        # 初始化 etl_config 和 pipeline 的关系数据
        etl_config_data = self._refine_etl_config(data_id_name, data_id_etl_config)
        data_id_pipeline_name = self._refine_data_id_pipeline(data_id_pipeline)
        self._init_etl_config_pipeline(etl_config_data, data_id_pipeline_name)
        # 初始化 data_id 和 pipeline 的关系数据
        self._init_data_id_pipeline(data_id_pipeline_name)
        # 初始化空间数据和 pipeline 的关系数据
        self._init_space_pipeline(data_id_pipeline_name)

        self.stdout.write("init datapipeline successfully")

    def _init_pipeline(self, data_id_kafka: Dict, data_id_transfer: Dict, data_id_rt: Dict) -> Dict:
        """初始化管道
        仅初始化完管道数据，然后再分配到数据源 ID
        """
        # 组装数据
        data = []
        data_id_pipeline = {}
        for data_id, kafka in data_id_kafka.items():
            # 获取 transfer 集群
            transfer_cluster = data_id_transfer.get(data_id)
            if not transfer_cluster:
                self.stderr.write(f"data_id: {data_id} not found transfer cluster")
                continue
            # NOTE: (vm|influxdb|es) 并存不好分配，暂时不允许并存
            table_ids = data_id_rt.get(data_id)
            _data = self._compose_pipeline_data(table_ids, kafka, transfer_cluster)
            data.extend(_data)
            # 组装 data id 所属的 pipeline
            data_id_pipeline[data_id] = _data
        # 去重
        data = list(set(data))
        # 构建批量创建数据
        bulk_create_data = [
            models.DataPipeline(
                name=f"{self.name_prefix}_{i}",  # 这里的名称怎样赋值
                chinese_name=f"{self.name_prefix}_{i}",
                kafka_cluster_id=d[0],
                transfer_cluster_id=d[1],
                influxdb_storage_cluster_id=d[2],
                kafka_storage_cluster_id=d[3],
                es_storage_cluster_id=d[4],
                vm_storage_cluster_id=d[5],
            )
            for i, d in enumerate(data)
        ]
        models.DataPipeline.objects.bulk_create(bulk_create_data)
        self.stdout.write("init datapipeline successfully")

        return data_id_pipeline

    def _init_etl_config_pipeline(self, etl_config_data: Dict, data_id_pipeline_name: Dict):
        """初始化数据场景和管道的关联关系"""
        event_data_id_list = etl_config_data["event_data_id_list"]
        apm_data_id_list = etl_config_data["apm_data_id_list"]
        log_data_id_list = etl_config_data["log_data_id_list"]
        alert_data_id_list = etl_config_data["alert_data_id_list"]
        metric_data_id_list = etl_config_data["metric_data_id_list"]

        bulk_create_data = []
        data_pipeline_name_etl_config = {}
        # 已使用的数据源中，一个 data id 应该属于一个类型
        for data_id, pipeline_name in data_id_pipeline_name.items():
            if data_id in event_data_id_list:
                etl_config = ETLConfig.EVENT.value
            elif data_id in apm_data_id_list:
                etl_config = ETLConfig.APM.value
            elif data_id in log_data_id_list:
                etl_config = ETLConfig.LOG.value
            elif data_id in alert_data_id_list:
                etl_config = ETLConfig.ALERT.value
            elif data_id in metric_data_id_list:
                etl_config = ETLConfig.METRIC.value
            else:
                self.stderr.write(f"etl config not found {data_id}")
                continue
            # 如果类型已经存在，则忽略
            if etl_config in (data_pipeline_name_etl_config.get(pipeline_name) or []):
                continue
            data_pipeline_name_etl_config.setdefault(pipeline_name, []).append(etl_config)

            bulk_create_data.append(
                models.DataPipelineEtlConfig(
                    data_pipeline_name=pipeline_name,
                    etl_config=etl_config,
                )
            )
        models.DataPipelineEtlConfig.objects.bulk_create(bulk_create_data)
        self.stdout.write("init datapipeline and etl config successfully")

    def _init_data_id_pipeline(self, data_id_pipeline_name: Dict):
        """初始化数据源 id 和管道的关系"""
        bulk_create_data = [
            models.DataPipelineDataSource(data_pipeline_name=pipeline_name, bk_data_id=data_id)
            for data_id, pipeline_name in data_id_pipeline_name.items()
        ]
        models.DataPipelineDataSource.objects.bulk_create(bulk_create_data)
        self.stdout.write("init datapipeline and datasource successfully")

    def _init_space_pipeline(self, data_id_pipeline_name: Dict):
        """初始化空间数据和管道的关系"""
        # 获取数据源和空间的关系
        data_id_space_dict = self._get_space_data_id()
        data_id_space_type_dict = self._get_space_type_data_id()
        # 组装数据
        bulk_create_data = []
        data_id_pipeline_name_space = {}
        for data_id, pipeline_name in data_id_pipeline_name.items():
            if data_id in data_id_space_dict:
                spaces = data_id_space_dict[data_id]
            elif data_id in data_id_space_type_dict:
                spaces = data_id_space_type_dict[data_id]
            else:
                self.stderr.write("data_id not found")
                continue

            for space in spaces:
                if space in (data_id_pipeline_name_space.get(pipeline_name) or set()):
                    continue
                data_id_pipeline_name_space.setdefault(pipeline_name, set()).add(spaces)
                bulk_create_data.append(
                    models.DataPipelineSpace(data_pipeline_name=pipeline_name, space_type=space[0], space_id=space[1])
                )
        # 创建记录
        models.DataPipelineSpace.objects.bulk_create(bulk_create_data)
        self.stdout.write("init datapipeline and space successfully")

    def _refine_etl_config(self, data_id_name: Dict, data_id_etl_config: Dict) -> Dict:
        """获取使用场景类型

        - 枚举已经使用的 data id，进行分类
        - 过滤出集群的 data id， 匹配 `_BCS-K8S-`
        - 过滤 `bk_standard_v2_event` 为 event 类型
        - 过滤到 data id 匹配的 rt， 然后进行匹配
            - table_id 以 bkapm_ 开头或者以 apm_global 开头或者包含 _bkapm，则为 apm 类型
            - table_id 包含 _bklog，则为 log 类型
        - 其它为 metric
        """
        # 过滤 event 类型
        event_data_id_list = [
            data_id for data_id, etl_config in data_id_etl_config.items() if etl_config == "bk_standard_v2_event"
        ]
        # 获取告警类型数据源 ID
        alert_data_id_list = []
        for data_id, name in data_id_name.items():
            if "_alert" not in name or data_id in event_data_id_list:
                continue
            alert_data_id_list.append(data_id)
        # 过滤 apm 和 log
        qs = models.DataSourceResultTable.objects.filter(
            bk_data_id__in=[
                data_id for data_id, etl_config in data_id_etl_config.items() if etl_config == "bk_flat_batch"
            ]
        )
        apm_data_id_list = list(
            qs.filter(
                Q(table_id__startswith="bkapm_") | Q(table_id__startswith="apm_global") | Q(table_id__contains="_bkapm")
            )
            .values_list("bk_data_id", flat=True)
            .distinct()
        )
        log_data_id_list = list(qs.filter(table_id__contains="_bklog").values_list("bk_data_id", flat=True).distinct())
        # 组装需要的数据
        event_data_id_set = set(event_data_id_list + self.internal_data_ids[ETLConfig.EVENT.value])
        alert_data_id_set = set(alert_data_id_list + self.internal_data_ids[ETLConfig.ALERT.value])
        metric_data_id_list = list(
            set(data_id_name.keys())
            - event_data_id_set
            - set(apm_data_id_list)
            - set(log_data_id_list)
            - set(alert_data_id_list)
        )

        return {
            "event_data_id_list": list(event_data_id_set),
            "apm_data_id_list": apm_data_id_list,
            "log_data_id_list": log_data_id_list,
            "alert_data_id_list": list(alert_data_id_set),
            "metric_data_id_list": metric_data_id_list,
        }

    def _refine_data_id_pipeline(self, data_id_pipeline: Dict) -> Dict:
        """获取数据源 ID 和 pipeline 的关系"""
        qs = models.DataPipeline.objects.all()
        pipeline_name_map = {
            (
                obj.kafka_cluster_id,
                obj.transfer_cluster_id,
                obj.influxdb_storage_cluster_id,
                obj.kafka_storage_cluster_id,
                obj.es_storage_cluster_id,
                obj.vm_storage_cluster_id,
            ): obj.name
            for obj in qs
        }
        data_id_pipeline_name = {}
        # 组装匹配数据
        for data_id, pipeline in data_id_pipeline.items():
            if pipeline and pipeline[0] in pipeline_name_map:
                data_id_pipeline_name[data_id] = pipeline_name_map[pipeline[0]]

        return data_id_pipeline_name

    def _compose_pipeline_data(self, table_ids: List, kafka: str, transfer_cluster: str) -> List:
        unique_key = (kafka, transfer_cluster)
        data = []
        if not table_ids:
            data.append(unique_key + (None, None, None, None))
            return data
        # 如果存在存储，则组装数据
        rt_vm, rt_influxdb = self._get_rt_influxdb_vm()
        rt_storage_kafka = self._get_rt_storage_kafka()
        rt_es = self._get_rt_es()

        for table_id in table_ids:
            _unique_key = unique_key + (
                rt_influxdb.get(table_id),
                rt_storage_kafka.get(table_id),
                rt_es.get(table_id),
                rt_vm.get(table_id),
            )
            data.append(_unique_key)
        return data

    def _get_rt_influxdb_vm(self) -> Tuple:
        """获取 rt 和 influxdb 存储的关系"""
        # 获取 vm 集群 ID
        vm_cluster_ids = models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_VM).values_list(
            "cluster_id", flat=True
        )

        rt_vm, rt_influxdb = {}, {}
        # 后端存储仅包含 vm 和 influxdb
        for qs in models.InfluxDBStorage.objects.values("table_id", "storage_cluster_id"):
            if qs["storage_cluster_id"] in vm_cluster_ids:
                rt_vm[qs["table_id"]] = qs["storage_cluster_id"]
            else:
                rt_influxdb[qs["table_id"]] = qs["storage_cluster_id"]

        return rt_vm, rt_influxdb

    def _get_rt_storage_kafka(self):
        """获取 rt 和 kafka 存储的关系"""
        return {
            qs["table_id"]: qs["storage_cluster_id"]
            for qs in models.KafkaStorage.objects.values("table_id", "storage_cluster_id")
        }

    def _get_rt_es(self):
        """获取 rt 和 es 存储的关系"""
        return {
            qs["table_id"]: qs["storage_cluster_id"]
            for qs in models.ESStorage.objects.values("table_id", "storage_cluster_id")
        }

    def _get_data_source(self) -> Tuple:
        """获取数据源 ID 和 名称及 transfer 集群"""
        qs = models.DataSource.objects.values(
            "bk_data_id", "data_name", "mq_cluster_id", "transfer_cluster_id", "etl_config"
        )

        data_id_name, data_id_etl_config, data_id_kafka, data_id_transfer = {}, {}, {}, {}
        for obj in qs:
            # 返回数据源 id 和名称
            data_id_name.update({obj["bk_data_id"]: obj["data_name"]})
            # 返回数据源 id 和 etl_config
            data_id_etl_config.update({obj["bk_data_id"]: obj["etl_config"]})
            # 返回数据源 id 和使用的 transfer 集群
            data_id_transfer.update({obj["bk_data_id"]: obj["transfer_cluster_id"]})
            # 返回数据源 id 和使用的 kafka 集群
            data_id_kafka.update({obj["bk_data_id"]: obj["mq_cluster_id"]})

        return data_id_name, data_id_etl_config, data_id_kafka, data_id_transfer

    def _get_data_id_rt(self) -> Dict:
        qs = models.DataSourceResultTable.objects.values("bk_data_id", "table_id")
        # 组装数据
        data = {}
        for obj in qs:
            data.setdefault(obj["bk_data_id"], []).append(obj["table_id"])
        return data

    def _get_space_data_id(self) -> Dict:
        """获取空间范围下的 data id"""
        qs = models.SpaceDataSource.objects.filter(from_authorization=False).values(
            "space_type_id", "space_id", "bk_data_id"
        )
        data = {}
        for obj in qs:
            data.setdefault(obj["bk_data_id"], []).append((obj["space_type_id"], obj["space_id"]))
        return data

    def _get_space_type_data_id(self) -> Dict:
        """获取空间类型所属的数据源 ID

        NOTE: 包含全空间类型
        """
        data = {}
        for space_types in constants.SpaceTypes._choices_labels.value:
            space_type = space_types[-1]
            data_ids = models.DataSource.objects.filter(is_platform_data_id=True, space_type_id=space_type).values_list(
                "bk_data_id", flat=True
            )
            for data_id in data_ids:
                # 补上 space id，便于后续进行匹配
                data.setdefault(data_id, []).append((space_type, None))
        return data

    def _set_default_pipeline(self):
        """设置默认管道"""
        # 默认管道的模块数据
        default_clusters = models.ClusterInfo.objects.filter(is_default_cluster=True)
        default_kafka = default_clusters.filter(cluster_type=models.ClusterInfo.TYPE_KAFKA).first()
        default_es = default_clusters.filter(cluster_type=models.ClusterInfo.TYPE_ES).first()
        default_influxdb = default_clusters.filter(cluster_type=models.ClusterInfo.TYPE_INFLUXDB).first()
        # 如果有任何一个不存在，则返回
        if not (default_kafka and default_es and default_influxdb):
            self.stderr.write("default kafka、es or influxdb not found")
            return
        # 获取集群 ID
        default_kafka_id = default_kafka.cluster_id
        default_influxdb_id = default_influxdb.cluster_id
        default_es = default_es.cluster_id
        default_transfer = settings.DEFAULT_TRANSFER_CLUSTER_ID
        # 现阶段 vm 先不作为默认存储的一个模块
        filter_pipeline_data = {
            "kafka_cluster_id": default_kafka_id,
            "transfer_cluster_id": default_transfer,
            "influxdb_storage_cluster_id": default_influxdb_id,
            "kafka_storage_cluster_id": None,
            "es_storage_cluster_id": default_es,
            "vm_storage_cluster_id": None,
        }
        default_name = f"{self.name_prefix}_default"
        models.DataPipeline.objects.update_or_create(
            **filter_pipeline_data, defaults={"is_default": True, "name": default_name, "chinese_name": default_name}
        )
        self.stdout.write(
            f"set default cluster, kafka: {default_kafka_id}, transfer: {default_transfer}, "
            f"influxdb: {default_influxdb_id}, es: {default_es}"
        )

        # 设置所属空间
        models.DataPipelineSpace.objects.update_or_create(
            data_pipeline_name=default_name, defaults={"space_type": constants.SpaceTypes.ALL.value}
        )
        # 设置数据场景
        models.DataPipelineEtlConfig.objects.update_or_create(
            data_pipeline_name=default_name, defaults={"etl_config": ETLConfig.ALL.value}
        )

        self.stdout.write(f"set default pipeline with space and etl config successfully")
