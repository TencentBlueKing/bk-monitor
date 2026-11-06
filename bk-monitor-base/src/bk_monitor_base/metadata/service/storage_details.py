import logging
from collections.abc import Callable
from typing import Any

import kafka
from django.db.models import Q

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.metadata import config, models
from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.models.space.space_data_source import get_real_biz_id

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

    def get_detail(self) -> list[dict[str, Any]]:
        detail: dict[str, Any] = self.get_basic_detail(self.bk_data_id)

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
        data: list[dict[str, Any]] = []
        for table_id, data_id in table_id_data_id.items():
            _detail: dict[str, Any] = {}
            if not detail or self.bcs_cluster_id:
                detail = self.get_basic_detail(data_id)
            _detail.update(detail)
            _detail.update(self.get_table_id(table_id))
            _detail.update(self.get_biz_info(table_id, detail["data_source"]))
            _detail.update(self.get_storage_cluster(table_id))
            _detail.update(self.get_influxdb_instance_cluster(table_id))
            data.append(_detail)
        return data

    def get_basic_detail(self, data_id: int | None) -> dict[str, Any]:
        detail = {}
        # 如果传递的数据源，则查询数据源信息
        if data_id:
            detail: dict[str, Any] = {"data_source": self.get_data_source(data_id)}
            detail.update(self.get_clusters(data_id))
            if self.with_gse_router:
                detail.update({"gse_router": self.query_gse_router(data_id)})
        return detail

    def query_gse_router(self, bk_data_id: int) -> dict[Any, list[Any]]:
        """查询GSE路由信息"""
        params = {
            "condition": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": bk_data_id},
            "operation": {"operator_name": settings.blueking.common_username},
        }
        try:
            result = api.gse.query_route(bk_tenant_id=self.bk_tenant_id, **params)
        except BkApiError as e:
            logger.error("query gse router error, %s", e)
            return {}
        if not result:
            return {}
        routers = result[0].get("route") or []
        if not routers:
            return {}
        data: dict[Any, list[Any]] = {}
        for router in routers:
            stream_to = router.get("stream_to") or {}
            stream_to_id = stream_to.get("stream_to_id")
            data.setdefault(stream_to_id, []).append(
                {"topic_name": stream_to["kafka"]["topic_name"], "name": router.get("name")}
            )
        return data

    def get_data_source(self, bk_data_id: int) -> dict[str, Any]:
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

    def get_table_id(self, table_id: str) -> dict[str, Any]:
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

    def get_table_id_data_id(self) -> dict[str, Any]:
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

    def get_biz_info(self, table_id: str, data_source: dict[str, Any]) -> dict[str, Any]:
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
            _, biz_list = api.cmdb.search_business(
                bk_tenant_id=self.bk_tenant_id,
                condition={"bk_biz_id": bk_biz_id},
            )
            bk_biz_name = biz_list[0].bk_biz_name
        except Exception:
            logger.error("biz: %s not found", bk_biz_id)
            bk_biz_name = ""
        return {"bk_biz_info": {"bk_biz_id": bk_biz_id, "bk_biz_name": bk_biz_name}}

    def get_clusters(self, bk_data_id: int) -> dict[str, Any]:
        try:
            ds = models.DataSource.objects.get(bk_tenant_id=self.bk_tenant_id, bk_data_id=bk_data_id)
        except Exception:
            raise Exception(f"bk_data_id: {bk_data_id} not found")
        cluster_info: dict[str, Any] = {"transfer_cluster": ds.transfer_cluster_id, "kafka_config": {}}
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

    def get_storage_cluster(self, table_id: str) -> dict[str, Any]:
        """获取存储相关信息"""
        storage_dict: dict[str, Any] = {}
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

    def get_influxdb_instance_cluster(self, table_id: str) -> dict[str, Any]:
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
        type_func_map: dict[str, Callable[..., list[dict[str, Any]]]] = {
            models.ClusterInfo.TYPE_KAFKA: cls.get_kafka_detail,
            models.ClusterInfo.TYPE_INFLUXDB: cls.get_influxdb_proxy_detail,
            models.ClusterInfo.TYPE_ES: cls.get_es_detail,
            models.ClusterInfo.TYPE_VM: cls.get_vm_details,
        }
        obj: models.ClusterInfo = cls.get_cluster(bk_tenant_id=bk_tenant_id, cluster_id=int(cluster_id))
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
            brokers: dict[str, Any] = client.brokers
            topics: dict[str, dict[str, Any]] = client.topic_partitions
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
        id_broker_map: dict[str, dict[str, Any]] = {
            broker_id: {"host": data.host, "port": data.port} for broker_id, data in brokers.items()
        }
        id_topic_map: dict[str, list[str]] = {}
        for topic, data in topics.items():
            for __, _id in data.items():
                id_topic_map.setdefault(_id, []).append(topic)

        # 返回数据
        result: list[dict[str, Any]] = []
        for _id, broker in id_broker_map.items():
            item = broker.copy()
            item["topic_count"] = len(id_topic_map.get(_id) or [])
            item["version"] = cluster_obj.version
            item["schema"] = cluster_obj.schema
            result.append(item)

        return result

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
