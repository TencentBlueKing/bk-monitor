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
from typing import Dict, List, Optional

from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet

from metadata.models.data_pipeline import constants, utils

logger = logging.getLogger("metadata")


class DataPipelineManager(models.Manager):
    def filter_data(
        self, name: Optional[str] = None, chinese_name: Optional[str] = None, is_enable: Optional[str] = "all"
    ) -> QuerySet:
        """根据条件过滤数据"""
        filter_params = {}
        if name:
            filter_params.update({"name__icontains": name})
        if chinese_name:
            filter_params.update({"chinese_name__icontains": chinese_name})
        if is_enable is not None:
            filter_params.update({"is_enable": is_enable})

        return self.filter(**filter_params)

    def check_name_exist(self, name: str) -> bool:
        """检测名称是否存在"""
        if self.filter(name=name).exists():
            return True
        return False

    def create_record(
        self,
        name: str,
        kafka_cluster_id: int,
        transfer_cluster_id: str,
        username: str,
        chinese_name: Optional[str] = "",
        label: Optional[str] = "",
        influxdb_storage_cluster_id: Optional[int] = None,
        kafka_storage_cluster_id: Optional[int] = None,
        es_storage_cluster_id: Optional[int] = None,
        vm_storage_cluster_id: Optional[int] = None,
        is_enable: Optional[bool] = True,
        description: Optional[str] = "",
    ) -> str:
        """
        创建记录

        :param name: 链路名称
        :param kafka_cluster_id: kafka 消息队列 ID
        :param transfer_cluster_id: transfer 集群 ID
        :param username: 用户名称
        :param chinese_name: 链路中文名称
        :param label: 链路的标签
        :param influxdb_storage_cluster_id: influxdb 集群 ID
        :param kafka_storage_cluster_id: kafka 存储集群 ID
        :param es_storage_cluster_id: es 存储集群 ID
        :param vm_storage_cluster_id: vm 存储集群 ID
        :param is_enable: 是否开启
        :param description: 链路的描述信息
        :return: 链路名称
        """
        # 下面的相关校验放在底层，防止每个调用的再校验一次
        # 1. 校验名称是否重复
        if self.filter(name=name).exists():
            raise ValueError("name: %s has exist", name)

        # 2. 校验存在
        # 2.1 校验 kafka 消息队列存在
        if not utils.check_kafka_cluster_exist(kafka_cluster_id):
            raise ValueError("kafka cluster: %s not exist", kafka_cluster_id)
        # 2.2 校验 transfer 集群存在
        if not utils.check_transfer_cluster_exist(transfer_cluster_id):
            raise ValueError("transfer cluster: %s not exist", transfer_cluster_id)
        # 2.3 校验存储集群存在
        if kafka_storage_cluster_id and not utils.check_kafka_cluster_exist(kafka_storage_cluster_id):
            raise ValueError("kafka storage cluster: %s not exist", kafka_storage_cluster_id)
        if influxdb_storage_cluster_id and not utils.check_influxdb_cluster_exist(influxdb_storage_cluster_id):
            raise ValueError("influxdb storage cluster: %s not exist", influxdb_storage_cluster_id)
        if es_storage_cluster_id and not utils.check_es_cluster_exist(es_storage_cluster_id):
            raise ValueError("es storage cluster: %s not exist", es_storage_cluster_id)
        if vm_storage_cluster_id and not utils.check_vm_cluster_exist(vm_storage_cluster_id):
            raise ValueError("vm storage cluster: %s not exist", vm_storage_cluster_id)

        # 创建记录
        self.create(
            name=name,
            chinese_name=chinese_name,
            label=label,
            kafka_cluster_id=kafka_cluster_id,
            transfer_cluster_id=transfer_cluster_id,
            influxdb_storage_cluster_id=influxdb_storage_cluster_id,
            kafka_storage_cluster_id=kafka_storage_cluster_id,
            es_storage_cluster_id=es_storage_cluster_id,
            vm_storage_cluster_id=vm_storage_cluster_id,
            is_enable=is_enable,
            description=description,
            creator=username,
            updater=username,
        )
        return name

    def get_name_by_cluster_ids(self, cluster_id_list: List) -> Dict:
        """通过集群 ID 获取链路名称"""
        # 过滤数据
        qs_data = self.filter(
            Q(kafka_cluster_id__in=cluster_id_list)
            | Q(transfer_cluster_id__in=cluster_id_list)
            | Q(influxdb_storage_cluster_id__in=cluster_id_list)
            | Q(kafka_storage_cluster_id__in=cluster_id_list)
            | Q(es_storage_cluster_id__in=cluster_id_list)
        ).values(
            "name",
            "chinese_name",
            "kafka_cluster_id",
            "transfer_cluster_id",
            "influxdb_storage_cluster_id",
            "kafka_storage_cluster_id",
            "es_storage_cluster_id",
        )
        names = {}
        # 组装集群对应的名称
        for data in qs_data:
            name = data["name"]
            kafka_cluster_id = data["kafka_cluster_id"]
            transfer_cluster_id = data["transfer_cluster_id"]
            influxdb_storage_cluster_id = data["influxdb_storage_cluster_id"]
            kafka_storage_cluster_id = data["kafka_storage_cluster_id"]
            es_storage_cluster_id = data["es_storage_cluster_id"]
            if kafka_cluster_id:
                names[kafka_cluster_id] = name
            if transfer_cluster_id:
                names[transfer_cluster_id] = name
            if influxdb_storage_cluster_id:
                names[influxdb_storage_cluster_id] = name
            if kafka_storage_cluster_id:
                names[kafka_storage_cluster_id] = name
            if es_storage_cluster_id:
                names[es_storage_cluster_id] = name
        return names


class DataPipelineEtlConfigManager(models.Manager):
    def filter_data(
        self, data_pipeline_name_list: Optional[List[str]] = None, etl_config: Optional[str] = None
    ) -> QuerySet:
        """根据条件过滤数据"""
        filter_params = {}
        # 组装过滤参数
        if etl_config:
            filter_params.update({"etl_config__icontains": etl_config})
        if data_pipeline_name_list:
            filter_params.update({"data_pipeline_name__in": data_pipeline_name_list})

        return self.filter(**filter_params)

    def create_record(
        self, data_pipeline_name: str, etl_configs: List[str], username: str, is_default: Optional[bool] = False
    ):
        """创建链路的使用场景记录
        :param data_pipeline_name: 链路名称
        :etl_configs: 场景类型
        :is_default: 是否默认
        """
        data = [
            self.model(
                data_pipeline_name=data_pipeline_name,
                etl_config=ec,
                is_default=is_default,
                creator=username,
                updater=username,
            )
            for ec in etl_configs
        ]
        self.bulk_create(data)

    def update_record(
        self, data_pipeline_name: str, etl_configs: List[str], username: str, is_default: Optional[bool] = False
    ):
        """更新记录
        :param data_pipeline_name: 链路名称
        :etl_configs: 场景类型
        :is_default: 是否默认
        """
        self.filter(data_pipeline_name=data_pipeline_name, etl_config__in=etl_configs).update(
            is_default=is_default, updater=username
        )


class DataPipelineSpaceManager(models.Manager):
    def filter_data(
        self,
        data_pipeline_name_list: Optional[List[str]] = None,
        space_type: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> QuerySet:
        """根据条件过滤数据"""
        filter_params = {}
        # 组装过滤参数
        if space_type:
            filter_params.update({"space_type__icontains": space_type})
        if space_id:
            filter_params.update({"space_id__icontains": space_type})
        if data_pipeline_name_list:
            filter_params.update({"data_pipeline_name__in": data_pipeline_name_list})

        return self.filter(**filter_params)

    def create_record(
        self, data_pipeline_name: str, spaces: List[Dict], username: str, is_default: Optional[bool] = False
    ):
        """创建记录
        :param data_pipeline_name: 链路名称
        :spaces: 空间信息
        :is_default: 是否默认
        """
        data = [
            self.model(
                data_pipeline_name=data_pipeline_name,
                space_type=space["space_type"],
                space_id=space["space_id"],
                is_default=is_default,
                creator=username,
                updater=username,
            )
            for space in spaces
        ]
        self.bulk_create(data)

    def update_record(
        self, data_pipeline_name: str, spaces: List[str], username: str, is_default: Optional[bool] = False
    ):
        """更新记录
        :param data_pipeline_name: 链路名称
        :spaces: 空间信息
        :is_default: 是否默认
        """
        filter_params = Q()
        for space in spaces:
            filter_params |= Q(**space)
        self.filter(filter_params, data_pipeline_name=data_pipeline_name).update(
            is_default=is_default, updater=username
        )


class DataPipelineDataSourceManager(models.Manager):
    def filter_data_source(
        self,
        data_pipeline_name: str,
        page: Optional[int] = constants.MIN_PAGE_NUM,
        page_size: Optional[int] = constants.DEFAULT_PAGE_SIZE,
    ) -> List:
        from metadata.models import DataSource, SpaceDataSource

        """过滤数据源信息"""
        data_ids = self.filter(data_pipeline_name=data_pipeline_name).values_list("bk_data_id", flat=True)
        # 获取 data_id 所属的空间信息
        data_id_space = {
            obj["bk_data_id"]: {"space_type_id": obj["space_type_id"], "space_id": obj["space_id"]}
            for obj in SpaceDataSource.objects.filter(bk_data_id__in=data_ids, from_authorization=False).values(
                "space_type_id", "space_id", "bk_data_id"
            )
        }
        # 获取数据源的详情
        data_source = DataSource.objects.filter(bk_data_id__in=data_ids)
        # 组装需要的数据
        ret_data = {"total": data_source.count(), "data": []}
        if not data_source:
            return ret_data
        start, end = (page - 1) * page_size, page * page_size
        for ds in data_source[start:end]:
            try:
                data_source_data = ds.to_json()
            except Exception as e:
                logger.error("pipeline datasource to json error, %s", e)
                data_source_data = {}
            data_source_data["space"] = data_id_space.get(ds.bk_data_id) or {}
            ret_data["data"].append(data_source_data)

        return ret_data
