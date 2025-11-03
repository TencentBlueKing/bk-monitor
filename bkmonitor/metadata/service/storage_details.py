"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

import kafka
from django.conf import settings
from django.db.models import Q

from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config, models
from metadata.models.space.space_data_source import get_real_biz_id

logger = logging.getLogger("metadata")


class ResultTableAndDataSource:
    def __init__(
        self,
        bk_tenant_id: str,
        table_id: str | None = None,
        bk_data_id: int | None = None,
        bcs_cluster_id: str | None = None,
        vm_table_id: str | None = None,
        metric_name: str | None = None,
        data_label: str | None = None,
        with_gse_router: bool | None = False,
    ):
        self.bk_tenant_id = bk_tenant_id
        self.bk_data_id = bk_data_id
        self.table_id = table_id
        self.bcs_cluster_id = bcs_cluster_id
        self.metric_name = metric_name
        self.vm_table_id = vm_table_id
        self.data_label = data_label
        self.with_gse_router = with_gse_router

    def get_detail(self):
        detail = self.get_basic_detail(self.bk_data_id)

        # 获取table id和data id
        try:
            table_id_data_id = self.get_table_id_data_id()
        except Exception as e:
            logger.error("get table_id and data_id error, error: %s", e)
            table_id_data_id = {}

        # 如果都不存在，则直接返回
        if not (detail or table_id_data_id):
            return []

        # 如果存在数据源基本信息，但是没有对应后续的链路信息，则直接返回
        if detail and not table_id_data_id:
            return [detail]
        # 组装获取数据详情
        data = []
        for table_id, data_id in table_id_data_id.items():
            _detail = {}
            if not detail or self.bcs_cluster_id:
                detail = self.get_basic_detail(data_id)
            _detail.update(detail)
            _detail.update(self.get_table_id(table_id))
            _detail.update(self.get_biz_info(table_id, detail["data_source"]))
            _detail.update(self.get_storage_cluster(table_id))
            _detail.update(self.get_influxdb_instance_cluster(table_id))
            data.append(_detail)
        return data

    def get_basic_detail(self, data_id: int | None) -> dict:
        detail = {}
        # 如果传递的数据源，则查询数据源信息
        if data_id:
            detail = {"data_source": self.get_data_source(data_id)}
            detail.update(self.get_clusters(data_id))
            if self.with_gse_router:
                detail.update({"gse_router": self.query_gse_router(data_id)})
        return detail

    def query_gse_router(self, bk_data_id: int) -> dict:
        """查询GSE路由信息"""
        params = {
            "condition": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": bk_data_id},
            "operation": {"operator_name": settings.COMMON_USERNAME},
        }
        try:
            result = api.gse.query_route(**params)
        except BKAPIError as e:
            logger.error("query gse router error, %s", e)
            return {}
        if not result:
            return {}
        routers = result[0].get("route") or []
        if not routers:
            return {}
        data = {}
        for router in routers:
            stream_to = router.get("stream_to") or {}
            stream_to_id = stream_to.get("stream_to_id")
            data.setdefault(stream_to_id, []).append(
                {"topic_name": stream_to["kafka"]["topic_name"], "name": router.get("name")}
            )
        return data

    def get_data_source(self, bk_data_id: int) -> dict:
        """获取数据源信息

        :param bk_data_id: 数据源ID
        :return: 数据源信息，格式: {"bk_data_id": xxx, "bk_data_name": xxx}
        """
        try:
            ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        except Exception:
            raise Exception(f"bk_data_id: {bk_data_id} not found")

        # 如果是集群的数据源ID，则返回集群信息
        cluster_obj = (
            models.BCSClusterInfo.objects.filter(bk_tenant_id=self.bk_tenant_id)
            .filter(
                Q(K8sMetricDataID=bk_data_id)
                | Q(CustomMetricDataID=bk_data_id)
                | Q(K8sEventDataID=bk_data_id)
                | Q(CustomEventDataID=bk_data_id)
            )
            .first()
        )
        cluster_id = ""
        if cluster_obj:
            cluster_id = cluster_obj.cluster_id

        return {
            "bk_data_id": ds.bk_data_id,
            "bk_data_name": ds.data_name,
            "space_uid": ds.space_uid,
            "etl_config": ds.etl_config,
            "creator": ds.creator,
            "updater": ds.last_modify_user,
            "cluster_id": cluster_id,
            "is_enable": ds.is_enable,
            "create_time": ds.create_time.timestamp(),
            "created_from": ds.created_from,
        }

    def get_table_id(self, table_id: str) -> dict:
        """获取结果表信息"""
        try:
            rt = models.ResultTable.objects.get(bk_tenant_id=self.bk_tenant_id, table_id=table_id)
        except models.ResultTable.DoesNotExist:
            raise Exception(f"table_id: {table_id} not found")
        return {
            "result_table": {
                "table_id": rt.table_id,
                "result_table_name": rt.table_name_zh,
                "is_enable": rt.is_enable,
            }
        }

    def get_table_id_data_id(self) -> dict:
        """
        获取数据源ID和结果表ID

        1. 如果结果表或vm结果表存在，则以结果表查询数据源，这里仅存在一个
        2. 否则，如果数据源存在，则通过数据源查询结果表，这里可能会存在多个
        3. 否则，则按照过滤对应的数据源，然后查询到相应的结果表，一个集群会存在两个必要数据源
        """
        if self.table_id or self.vm_table_id or self.data_label:
            table_id = self.table_id
            # 通过 vm 结果表获取监控结果表
            if self.vm_table_id:
                table_id = models.AccessVMRecord.objects.get(
                    bk_tenant_id=self.bk_tenant_id, vm_result_table_id=self.vm_table_id
                ).result_table_id
            # 通过数据标签获取监控结果表
            elif self.data_label:
                table_id = models.ResultTable.objects.get(
                    bk_tenant_id=self.bk_tenant_id, data_label=self.data_label
                ).table_id

            obj = models.DataSourceResultTable.objects.get(bk_tenant_id=self.bk_tenant_id, table_id=table_id)
            return {obj.table_id: obj.bk_data_id}

        elif self.bk_data_id:
            return {
                obj.table_id: obj.bk_data_id
                for obj in models.DataSourceResultTable.objects.filter(
                    bk_tenant_id=self.bk_tenant_id, bk_data_id=self.bk_data_id
                )
            }
        else:
            cluster_record = models.BCSClusterInfo.objects.get(
                bk_tenant_id=self.bk_tenant_id, cluster_id=self.bcs_cluster_id
            )
            bk_data_id_list = [
                cluster_record.K8sMetricDataID,
                cluster_record.CustomMetricDataID,
                cluster_record.K8sEventDataID,
            ]

            tid_ds = {
                obj.table_id: obj.bk_data_id
                for obj in models.DataSourceResultTable.objects.filter(
                    bk_tenant_id=self.bk_tenant_id, bk_data_id__in=bk_data_id_list
                )
            }
            # 当指标存在时，根据指标过滤结果表
            if self.metric_name:
                tids = models.ResultTableField.objects.filter(
                    bk_tenant_id=self.bk_tenant_id, field_name=self.metric_name, table_id__in=tid_ds.keys()
                ).values_list("table_id", flat=True)
                return {tid: tid_ds[tid] for tid in tids}

            return tid_ds

    def get_biz_info(self, table_id: str, data_source: dict) -> dict:
        try:
            rt = models.ResultTable.objects.get(bk_tenant_id=self.bk_tenant_id, table_id=table_id)
        except Exception:
            logger.error("table_id: %s not found", table_id)
            return {}
        bk_biz_id = rt.bk_biz_id
        # 当结果表对应的业务ID为0时，需要通过下面函数转换为真正的业务ID
        if str(bk_biz_id) == "0":
            # 过滤数据源数据
            data_id = data_source["bk_data_id"]
            is_in_ts_group = models.TimeSeriesGroup.objects.filter(
                bk_tenant_id=self.bk_tenant_id, bk_data_id=data_id
            ).exists()
            is_in_event_group = models.EventGroup.objects.filter(
                bk_tenant_id=self.bk_tenant_id, bk_data_id=data_id
            ).exists()
            bk_biz_id = get_real_biz_id(
                data_source["bk_data_name"], is_in_ts_group, is_in_event_group, data_source.get("space_uid")
            )
        # 通过业务 ID 查询业务中文名称
        try:
            biz = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])[0]
            bk_biz_name = biz.bk_biz_name
        except Exception:
            logger.error("biz: %s not found", bk_biz_id)
            bk_biz_name = ""
        return {"bk_biz_info": {"bk_biz_id": bk_biz_id, "bk_biz_name": bk_biz_name}}

    def get_clusters(self, bk_data_id: int) -> dict:
        try:
            ds = models.DataSource.objects.get(bk_tenant_id=self.bk_tenant_id, bk_data_id=bk_data_id)
        except Exception:
            raise Exception(f"bk_data_id: {bk_data_id} not found")
        cluster_info = {"transfer_cluster": ds.transfer_cluster_id, "kafka_config": {}}
        # 获取 kafka 队列的信息
        try:
            kt = models.KafkaTopicInfo.objects.get(id=ds.mq_config_id)
        except Exception:
            logger.error("KafkaTopicInfo: %s not found", ds.mq_config_id)
            return cluster_info
        cluster_info["kafka_config"].update({"topic": kt.topic, "partition": kt.partition})
        try:
            c = models.ClusterInfo.objects.get(bk_tenant_id=self.bk_tenant_id, cluster_id=ds.mq_cluster_id)
        except Exception:
            logger.error("kafka ClusterInfo: %s not found", ds.mq_cluster_id)
            return cluster_info
        cluster_info["kafka_config"].update(
            {
                "cluster_name": c.cluster_name,
                "domain_name": c.domain_name,
                "port": c.port,
                "username": c.username,
                "password": c.password,
                "version": c.version,
                "schema": c.schema,
                "gse_stream_to_id": c.gse_stream_to_id,
            }
        )
        return cluster_info

    def get_storage_cluster(self, table_id: str) -> dict:
        """获取存储相关信息"""
        storage_dict = {}
        for storage_type, storage_cls in models.ResultTable.REAL_STORAGE_DICT.items():
            storage_info = storage_cls.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id)
            if not storage_info:
                storage_dict[storage_type] = {}
                continue
            storage_info = storage_info.first()
            try:
                config = storage_info.consul_config
            except storage_cls.DoesNotExist:
                config = {}
            except Exception as e:
                logger.error("get consul config error, %s", e)
                config = {}
            storage_dict[storage_type] = config

        # 通过结果表追加 vm 配置
        table_id_vm_obj = models.AccessVMRecord.objects.filter(
            bk_tenant_id=self.bk_tenant_id, result_table_id=table_id
        ).first()
        if table_id_vm_obj:
            try:
                vm_cluster_domain = models.ClusterInfo.objects.get(
                    bk_tenant_id=self.bk_tenant_id, cluster_id=table_id_vm_obj.vm_cluster_id
                ).domain_name
            except models.ClusterInfo.DoesNotExist:
                vm_cluster_domain = ""
            storage_dict[models.ClusterInfo.TYPE_VM] = {
                "vm_cluster_domain": vm_cluster_domain,
                "vm_cluster_id": table_id_vm_obj.vm_cluster_id,
                "bk_base_data_id": table_id_vm_obj.bk_base_data_id,
                "vm_result_table_id": table_id_vm_obj.vm_result_table_id,
            }
        else:
            storage_dict[models.ClusterInfo.TYPE_VM] = {}

        return storage_dict

    def get_influxdb_instance_cluster(self, table_id: str) -> dict:
        """获取结果表对应的influxdb实例集群信息"""
        try:
            influxdb_storage = models.InfluxDBStorage.objects.get(bk_tenant_id=self.bk_tenant_id, table_id=table_id)
        except models.InfluxDBStorage.DoesNotExist:
            return {"influxdb_instance_cluster": {}}
        influxdb_proxy_storage_id = influxdb_storage.influxdb_proxy_storage_id
        # 获取对应的集群
        try:
            influxdb_proxy_storage_obj = models.InfluxDBProxyStorage.objects.get(id=influxdb_proxy_storage_id)
        except models.InfluxDBProxyStorage.DoesNotExist:
            return {"influxdb_instance_cluster": {}}
        cluster_name = influxdb_proxy_storage_obj.instance_cluster_name
        cluster_info = models.InfluxDBClusterInfo.objects.filter(cluster_name=cluster_name).values(
            "host_name", "host_readable"
        )
        if not cluster_info:
            return {"influxdb_instance_cluster": {}}
        host_dict = {i["host_name"]: i for i in cluster_info}
        # 通过cluster info获取对应的主机 ip及密码信息
        qs = models.InfluxDBHostInfo.objects.filter(host_name__in=host_dict.keys())
        host_info_dict = {i.host_name: i.consul_config for i in qs}
        # 匹配数据
        for key, val in host_info_dict.items():
            if not host_dict.get(key):
                continue
            host_dict[key].update(val)
        # 返回数据
        return {"influxdb_instance_cluster": list(host_dict.values())}


class StorageClusterDetail:
    @classmethod
    def get_detail(cls, bk_tenant_id: str, cluster_id: str | int) -> list[dict[str, Any]]:
        type_func_map = {
            models.ClusterInfo.TYPE_KAFKA: cls.get_kafka_detail,
            models.ClusterInfo.TYPE_INFLUXDB: cls.get_influxdb_proxy_detail,
            models.ClusterInfo.TYPE_ES: cls.get_es_detail,
            models.ClusterInfo.TYPE_VM: cls.get_vm_details,
        }
        obj = cls.get_cluster(bk_tenant_id=bk_tenant_id, cluster_id=int(cluster_id))
        func = type_func_map.get(obj.cluster_type)
        if not func:
            raise ValueError("not support cluster type")
        return func(cluster_obj=obj)

    @classmethod
    def get_cluster(cls, bk_tenant_id: str, cluster_id: int) -> models.ClusterInfo:
        """获取集群信息"""
        try:
            return models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
        except models.ClusterInfo.DoesNotExist:
            logger.error("kafka cluster: %s not found", cluster_id)
            raise ValueError("cluster_id: %s not found", cluster_id)

    @classmethod
    def get_kafka_detail(cls, cluster_obj: models.ClusterInfo) -> list[dict[str, Any]]:
        # 获取 broker
        kafka_host = f"{cluster_obj.domain_name}:{cluster_obj.port}"
        try:
            client = kafka.KafkaClient(kafka_host)
            brokers = client.brokers
            topics = client.topic_partitions
        except Exception as e:
            logger.error("request kafka api error, %s", e)
            return [
                {
                    "host": cluster_obj.domain_name,
                    "port": cluster_obj.port,
                    "topic_count": 0,
                    "version": cluster_obj.version,
                    "schema": cluster_obj.schema,
                    "status": "running",
                }
            ]

        # 解析 broker 和 topic数据
        id_broker_map = {id: {"host": data.host, "port": data.port} for id, data in brokers.items()}
        id_topic_map = {}
        for topic, data in topics.items():
            for __, id in data.items():
                id_topic_map.setdefault(id, []).append(topic)

        # 返回数据
        data = []
        for id, broker in id_broker_map.items():
            item = broker.copy()
            item["topic_count"] = len(id_topic_map.get(id) or [])
            item["version"] = cluster_obj.version
            item["schema"] = cluster_obj.schema
            data.append(item)

        return data

    @classmethod
    def get_influxdb_proxy_detail(cls, cluster_obj: models.ClusterInfo) -> list[dict[str, Any]]:
        return [cls._get_cluster_detail(cluster_obj=cluster_obj)]

    @classmethod
    def get_es_detail(cls, cluster_obj: models.ClusterInfo) -> list[dict[str, Any]]:
        return [cls._get_cluster_detail(cluster_obj=cluster_obj)]

    @classmethod
    def get_vm_details(cls, cluster_obj: models.ClusterInfo) -> list[dict[str, Any]]:
        return [cls._get_cluster_detail(cluster_obj=cluster_obj)]

    @classmethod
    def _get_cluster_detail(cls, cluster_obj: models.ClusterInfo) -> dict[str, Any]:
        return {
            "host": cluster_obj.domain_name,
            "port": cluster_obj.port,
            "version": cluster_obj.version,
            "schema": cluster_obj.schema,
            "status": "running",
        }
