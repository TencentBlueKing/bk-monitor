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
import logging
from typing import Dict, List, Optional, Union

import kafka
import requests
from elasticsearch import Elasticsearch as Elasticsearch
from kafka.admin import KafkaAdminClient

from core.drf_resource import api
from metadata import models
from metadata.models.data_pipeline.utils import check_transfer_cluster_exist
from metadata.models.space.space_data_source import get_real_biz_id
from metadata.utils.es_tools import compose_es_hosts, get_client

logger = logging.getLogger("metadata")


class ResultTableAndDataSource:
    def __init__(
        self, table_id: Optional[str] = None, bk_data_id: Optional[int] = None, bcs_cluster_id: Optional[str] = None
    ):
        self.bk_data_id = bk_data_id
        self.table_id = table_id
        self.bcs_cluster_id = bcs_cluster_id

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
            if not detail:
                detail = self.get_basic_detail(data_id)
            detail.update(self.get_biz_info(table_id, detail["data_source"]))
            detail.update(self.get_storage_cluster(table_id))
            detail.update(self.get_influxdb_instance_cluster(table_id))
            data.append(detail)
        return data

    def get_basic_detail(self, data_id: int) -> Dict:
        detail = {}
        # 如果传递的数据源，则查询数据源信息
        if data_id:
            detail = {"data_source": self.get_data_source(data_id)}
            detail.update(self.get_clusters(data_id))
        return detail

    def get_data_source(self, bk_data_id: int) -> Dict:
        """获取数据源信息

        :param bk_data_id: 数据源ID
        :return: 数据源信息，格式: {"bk_data_id": xxx, "bk_data_name": xxx}
        """
        try:
            ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        except Exception:
            raise Exception(f"bk_data_id: {bk_data_id} not found")

        return {"bk_data_id": ds.bk_data_id, "bk_data_name": ds.data_name, "space_uid": ds.space_uid}

    def get_table_id_data_id(self) -> Dict:
        """
        获取数据源ID和结果表ID

        1. 如果结果表存在，则以结果表查询数据源，这里仅存在一个
        2. 否则，如果数据源存在，则通过数据源查询结果表，这里可能会存在多个
        3. 否则，则按照过滤对应的数据源，然后查询到相应的结果表，一个集群会存在两个必要数据源
        """
        if self.table_id:
            obj = models.DataSourceResultTable.objects.get(table_id=self.table_id)
            return {obj.table_id: obj.bk_data_id}
        elif self.bk_data_id:
            return {
                obj.table_id: obj.bk_data_id
                for obj in models.DataSourceResultTable.objects.filter(bk_data_id=self.bk_data_id)
            }
        else:
            cluster_record = models.BCSClusterInfo.objects.get(cluster_id=self.bcs_cluster_id)
            bk_data_id_list = [
                cluster_record.K8sMetricDataID,
                cluster_record.CustomMetricDataID,
            ]
            return {
                obj.table_id: obj.bk_data_id
                for obj in models.DataSourceResultTable.objects.filter(bk_data_id__in=bk_data_id_list)
            }

    def get_biz_info(self, table_id: str, data_source: Dict) -> Dict:
        try:
            rt = models.ResultTable.objects.get(table_id=table_id)
        except Exception:
            logger.error("table_id: %s not found", table_id)
            return {}
        bk_biz_id = rt.bk_biz_id
        # 当结果表对应的业务ID为0时，需要通过下面函数转换为真正的业务ID
        if str(bk_biz_id) == "0":
            # 过滤数据源数据
            data_id = data_source["bk_data_id"]
            is_in_ts_group = models.TimeSeriesGroup.objects.filter(bk_data_id=data_id).exists()
            is_in_event_group = models.EventGroup.objects.filter(bk_data_id=data_id).exists()
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

    def get_clusters(self, bk_data_id: int) -> Dict:
        try:
            ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
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
            c = models.ClusterInfo.objects.get(cluster_id=ds.mq_cluster_id)
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

    def get_storage_cluster(self, table_id: str) -> Dict:
        """获取存储相关信息"""
        storage_dict = {}
        for storage_type, storage_cls in models.ResultTable.REAL_STORAGE_DICT.items():
            storage_info = storage_cls.objects.filter(table_id=table_id)
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
        table_id_vm_obj = models.AccessVMRecord.objects.filter(result_table_id=table_id)
        if table_id_vm_obj:
            obj = table_id_vm_obj.first()
            storage_dict[models.ClusterInfo.TYPE_VM] = {
                "vm_cluster_id": obj.vm_cluster_id,
                "bk_base_data_id": obj.bk_base_data_id,
                "vm_result_table_id": obj.vm_result_table_id,
            }
        else:
            storage_dict[models.ClusterInfo.TYPE_VM] = {}

        return storage_dict

    def get_influxdb_instance_cluster(self, table_id: str) -> Dict:
        """获取结果表对应的influxdb实例集群信息"""
        influxdb_storage = models.InfluxDBStorage.objects.filter(table_id=table_id)
        if not influxdb_storage:
            return {"influxdb_instance_cluster": {}}
        influxdb_proxy_storage_id = influxdb_storage.first().influxdb_proxy_storage_id
        # 获取对应的集群
        influxdb_proxy_storage_objs = models.InfluxDBProxyStorage.objects.filter(id=influxdb_proxy_storage_id)
        if not influxdb_proxy_storage_objs.exists():
            return {"influxdb_instance_cluster": {}}
        cluster_name = influxdb_proxy_storage_objs.first().instance_cluster_name
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


class StorageCluster:
    @classmethod
    def get_cluster_type(self) -> List:
        """获取集群类型"""
        return list(models.ClusterInfo.objects.values_list("cluster_type", flat=True).distinct())

    @classmethod
    def get_all_clusters(cls):
        return {
            obj["cluster_id"]: obj["cluster_name"]
            for obj in models.ClusterInfo.objects.values("cluster_id", "cluster_name")
        }

    @classmethod
    def get_cluster_id_cluster_name(cls, cluster_id: Optional[int] = None, cluster_type: Optional[str] = None) -> Dict:
        """获取集群 id 和集群名称"""
        qs = models.ClusterInfo.objects.all()
        if not (cluster_id or cluster_type):
            return [
                {"cluster_id": obj.cluster_id, "cluster_name": obj.cluster_name, "cluster_type": obj.cluster_type}
                for obj in qs
            ]

        # 过滤数据
        if cluster_id:
            qs = qs.filter(cluster_id=cluster_id)
        if cluster_type:
            qs = qs.filter(cluster_type=cluster_type)

        # 返回内容
        if not qs.exists():
            err_msg = f"cluster_id: {cluster_id} not found"
            logger.error(err_msg)
            raise ValueError(err_msg)

        return [
            {"cluster_id": obj.cluster_id, "cluster_name": obj.cluster_name, "cluster_type": obj.cluster_type}
            for obj in qs
        ]


class ClusterHealthCheck:
    @classmethod
    def check(
        cls,
        cluster_id: Union[str, int, None] = None,
        cluster_type: Optional[str] = "",
        domain: Optional[str] = "",
        port: Optional[int] = 0,
        schema: Optional[str] = "",
        is_ssl_verify: Optional[bool] = False,
        username: Optional[str] = "",
        password: Optional[str] = "",
    ) -> bool:
        if cluster_type == "transfer":
            return cls.check_transfer_cluster(cluster_id)
        if cluster_type == models.ClusterInfo.TYPE_ES:
            obj = None
            if cluster_id:
                obj = cls.get_cluster(cluster_id)
            try:
                return cls.check_es_cluster(
                    cluster_obj=obj,
                    domain=domain,
                    port=port,
                    is_ssl_verify=is_ssl_verify,
                    username=username,
                    password=password,
                    schema=schema,
                )
            except Exception as e:
                logger.error("check es error, %s", e)
                return False
        type_func_map = {
            models.ClusterInfo.TYPE_ES: cls.check_es_cluster,
            models.ClusterInfo.TYPE_KAFKA: cls.check_kafka_cluster,
            models.ClusterInfo.TYPE_INFLUXDB: cls.check_influxdb_cluster,
            models.ClusterInfo.TYPE_VM: cls.check_vm_cluster,
        }
        # 设置默认值
        obj = None
        if cluster_id:
            obj = cls.get_cluster(cluster_id)
        if obj:
            cluster_type = obj.cluster_type
        func = type_func_map.get(cluster_type)
        if not func:
            raise ValueError("not support cluster type")
        host = ""
        if domain and port:
            host = f"{domain}:{port}"
        try:
            return func(cluster_obj=obj, host=host)
        except Exception as e:
            logger.error("check cluster status error, %s", e)
            return False

    @classmethod
    def get_cluster(cls, cluster_id: int) -> Optional[models.ClusterInfo]:
        """获取集群信息"""
        try:
            return models.ClusterInfo.objects.get(cluster_id=cluster_id)
        except models.ClusterInfo.DoesNotExist:
            logger.error("kafka cluster: %s not found", cluster_id)
            return None

    @classmethod
    def check_kafka_cluster(
        cls,
        kafka_cluster: Optional[int] = None,
        cluster_obj: Optional[models.ClusterInfo] = None,
        kafka_host: Optional[str] = "",
    ) -> bool:
        """检测 kafka 集群"""
        # 查询集群域名和端口
        if not cluster_obj and kafka_cluster:
            cluster_obj = cls.get_cluster(kafka_cluster)
            if not cluster_obj:
                return False

        # 测试 topic
        test_topic_name = "bkmonitor_health_check_topic"
        if cluster_obj:
            kafka_host = f"{cluster_obj.domain_name}:{cluster_obj.port}"
        try:
            client = kafka.KafkaClient(kafka_host)
            client.ensure_topic_exists(test_topic_name)
        except Exception as e:
            logger.error("create topic: %s error: %s", test_topic_name, e)
            return False

        # 获取 topic 存在
        if test_topic_name not in client.topic_partitions:
            return False

        # 删除 topic， 异常忽略
        try:
            admin_client = KafkaAdminClient(bootstrap_servers=kafka_host)
            admin_client.delete_topics([test_topic_name])
        except Exception as e:
            logger.error("delete topic: %s error: %s", test_topic_name, e)

        return True

    @classmethod
    def check_influxdb_cluster(
        cls,
        influxdb_cluster: Optional[int] = None,
        cluster_obj: Optional[models.ClusterInfo] = None,
        host: Optional[str] = "",
    ) -> bool:
        """检测 influxdb 集群"""
        # 查询集群域名和端口
        if not cluster_obj and influxdb_cluster:
            cluster_obj = cls.get_cluster(influxdb_cluster)
            if not cluster_obj:
                return False

        # 检测 metric
        if cluster_obj:
            host = f"{cluster_obj.domain_name}:{cluster_obj.port}"
        if not (host.startswith("http://") or host.startswith("https://")):
            host = f"http://{host}"
        try:
            resp = requests.get(f"{host}/metrics")
            # 非 200，则认为错误
            if resp.status_code != 200:
                logger.error("request influxdb proxy metric error: %s", resp.text)
                return False
        except Exception as e:
            logger.error("request influxdb proxy metric error: %s", e)
            return False

        return True

    @classmethod
    def check_es_cluster(
        cls,
        es_cluster: Optional[int] = None,
        cluster_obj: Optional[models.ClusterInfo] = None,
        domain: Optional[str] = "",
        port: Optional[int] = None,
        is_ssl_verify: Optional[bool] = False,
        username: Optional[str] = "",
        password: Optional[str] = "",
        schema: Optional[str] = "",
    ) -> bool:
        """检测 es 集群"""
        # 查询集群域名和端口
        if not cluster_obj and es_cluster:
            cluster_obj = cls.get_cluster(es_cluster)
            if not cluster_obj:
                return False

        if cluster_obj:
            client = get_client(cluster_obj)
            # 可以连通
            if client.ping():
                return True

        # 根据版本加载客户端
        connection_info = {
            "hosts": compose_es_hosts(domain, port),
            "verify_certs": is_ssl_verify,
            "use_ssl": is_ssl_verify,
        }
        if username and password:
            connection_info["http_auth"] = (username, password)

        if schema == "https":
            connection_info["scheme"] = schema
        es_client = Elasticsearch(**connection_info)
        if es_client.ping():
            return True
        return False

    @classmethod
    def check_transfer_cluster(cls, transfer_cluster: str) -> bool:
        """检测 transfer 集群，如果存在则认为是正常的"""
        return check_transfer_cluster_exist(transfer_cluster)

    @classmethod
    def check_vm_cluster(
        cls,
        vm_cluster: Optional[int] = None,
        cluster_obj: Optional[models.ClusterInfo] = None,
        host: Optional[str] = "",
    ) -> bool:
        return True


class StorageClusterDetail:
    @classmethod
    def get_detail(cls, cluster_id: Union[str, int]) -> List:
        type_func_map = {
            models.ClusterInfo.TYPE_KAFKA: cls.get_kafka_detail,
            models.ClusterInfo.TYPE_INFLUXDB: cls.get_influxdb_proxy_detail,
            models.ClusterInfo.TYPE_ES: cls.get_es_detail,
            models.ClusterInfo.TYPE_VM: cls.get_vm_details,
        }
        obj = cls.get_cluster(cluster_id)
        func = type_func_map.get(obj.cluster_type)
        if not func:
            raise ValueError("not support cluster type")
        return func(cluster_obj=obj)

    @classmethod
    def get_cluster(cls, cluster_id: int) -> Optional[models.ClusterInfo]:
        """获取集群信息"""
        try:
            return models.ClusterInfo.objects.get(cluster_id=cluster_id)
        except models.ClusterInfo.DoesNotExist:
            logger.error("kafka cluster: %s not found", cluster_id)
            raise ValueError("cluster_id: %s not found", cluster_id)

    @classmethod
    def get_kafka_detail(
        cls, cluster_id: Optional[int] = None, cluster_obj: Optional[models.ClusterInfo] = None
    ) -> List:
        # 查询集群域名和端口
        if not cluster_obj:
            cluster_obj = cls.get_cluster(cluster_id)
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
    def get_influxdb_proxy_detail(
        cls, cluster_id: Optional[int] = None, cluster_obj: Optional[models.ClusterInfo] = None
    ) -> List:
        # 查询集群域名和端口
        if not cluster_obj:
            cluster_obj = cls.get_cluster(cluster_id)

        # 返回数据
        return [
            {
                "host": cluster_obj.domain_name,
                "port": cluster_obj.port,
                "version": cluster_obj.version,
                "schema": cluster_obj.schema,
                "status": "running",
            }
        ]

    @classmethod
    def get_es_detail(cls, cluster_id: Optional[int] = None, cluster_obj: Optional[models.ClusterInfo] = None) -> List:
        # 查询集群域名和端口
        if not cluster_obj:
            cluster_obj = cls.get_cluster(cluster_id)

        # 返回数据
        return [
            {
                "host": cluster_obj.domain_name,
                "port": cluster_obj.port,
                "version": cluster_obj.version,
                "schema": cluster_obj.schema,
                "status": "running",
            }
        ]

    @classmethod
    def get_vm_details(cls, cluster_id: Optional[int] = None, cluster_obj: Optional[models.ClusterInfo] = None) -> List:
        # 查询集群域名和端口
        if not cluster_obj:
            cluster_obj = cls.get_cluster(cluster_id)

        # 返回数据
        return [
            {
                "host": cluster_obj.domain_name,
                "port": cluster_obj.port,
                "version": cluster_obj.version,
                "schema": cluster_obj.schema,
                "status": "running",
            }
        ]
