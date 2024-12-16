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
import logging
from typing import Dict, List, Optional

from django.db import models
from django.db.models import Q
from django.db.models.fields import DateTimeField
from django.db.transaction import atomic
from django.utils.translation import gettext_lazy as _lazy

from metadata import config
from metadata.models.common import BaseModel
from metadata.models.data_pipeline import constants, utils

from .managers import (
    DataPipelineDataSourceManager,
    DataPipelineEtlConfigManager,
    DataPipelineManager,
    DataPipelineSpaceManager,
)

logger = logging.getLogger("metadata")


class DataPipeline(BaseModel):
    name = models.CharField("链路管道名称", max_length=128, unique=True)
    chinese_name = models.CharField("链路管道中文名称", max_length=64, null=True, blank=True, help_text="如果不传递，可以和name保持一致")
    label = models.CharField("标签", max_length=256, null=True, blank=True, help_text="管道的标签")
    kafka_cluster_id = models.IntegerField("消息队列 kafka 集群 ID")
    transfer_cluster_id = models.CharField("transfer 集群 ID", max_length=64)
    influxdb_storage_cluster_id = models.IntegerField("influxdb 存储 id", null=True, blank=True)
    kafka_storage_cluster_id = models.IntegerField("kafka 存储集群 id", null=True, blank=True)
    es_storage_cluster_id = models.IntegerField("es 存储集群 id", null=True, blank=True)
    vm_storage_cluster_id = models.IntegerField("vm 存储集群 id", null=True, blank=True)
    is_enable = models.BooleanField("是否启用", default=True)
    description = models.TextField("链路描述信息", null=True, blank=True)

    objects = DataPipelineManager()

    class Meta:
        verbose_name = "数据链路信息"
        verbose_name_plural = "数据链路信息"

    def to_dict(self, fields: Optional[List] = None, exclude: Optional[List] = None) -> Dict:
        data = {}
        for f in self._meta.concrete_fields + self._meta.many_to_many:
            value = f.value_from_object(self)
            # 属性存在
            if fields and f.name not in fields:
                continue
            # 排除的属性
            if exclude and f.name in exclude:
                continue
            # 时间转换
            if isinstance(f, DateTimeField):
                value = value.strftime("%Y-%m-%d %H:%M:%S") if value else None

            data[f.name] = value

        return data

    @classmethod
    def filter_data(
        cls,
        name: Optional[str] = None,
        chinese_name: Optional[str] = None,
        etl_config: Optional[str] = None,
        space_type: Optional[str] = None,
        space_id: Optional[str] = None,
        is_enable: Optional[bool] = None,
        page_size: Optional[int] = constants.DEFAULT_PAGE_SIZE,
        page: Optional[int] = constants.MIN_PAGE_NUM,
    ) -> List[Dict]:
        """根据参数过滤数据

        :param name: 链路名称
        :param chinese_name: 链路中文名称
        :param etl_config: 链路类型
        :param space_type: 空间类型，标识可以使用范围
        :param space_id: 空间 ID，标识可以使用范围
        :param is_enable: 是否启用
        :param page_size: 每页的大小，默认为 10
        :param page: 页数，默认第一页
        :return: 过滤到的数据
        """
        # 返回数据
        ret_data = {"total": 0, "data": []}

        # 根据链路参数过滤数据，并按时间逆序
        data_pipeline_qs = cls.objects.filter_data(name, chinese_name, is_enable).order_by("-update_time")
        # 如果没有过滤到数据，直接返回
        if not data_pipeline_qs:
            return ret_data

        # 获取链路的映射，用以后面组装数据
        data_pipeline_map = {dp.name: dp for dp in data_pipeline_qs}
        # 过滤场景类型数据
        filter_name_list = list(data_pipeline_map.keys()) if (name or chinese_name) else []
        etl_conf_qs = DataPipelineEtlConfig.objects.filter_data(filter_name_list, etl_config)
        # 过滤使用范围数据
        space_qs = DataPipelineSpace.objects.filter_data(filter_name_list, space_type, space_id)

        # NOTE: 如果查询有一个为空，则返回为空
        if not (etl_conf_qs and space_qs):
            return ret_data

        # 管道名称和 etl config 的映射
        name_etl_conf_map = {}
        for obj in etl_conf_qs:
            name_etl_conf_map.setdefault(obj.data_pipeline_name, []).append(
                {"etl_config": obj.etl_config, "is_default": obj.is_default}
            )
        name_space_map = {}
        for obj in space_qs:
            name_space_map.setdefault(obj.data_pipeline_name, []).append(
                {"space_type": obj.space_type, "space_id": obj.space_id, "is_default": obj.is_default}
            )
        # 组装数据
        data = []
        for obj in data_pipeline_qs:
            name = obj.name
            etl_conf = name_etl_conf_map.get(name)
            space = name_space_map.get(name)
            if not (etl_conf and space):
                logger.error("name: %s not match etl_conf or space", name)
                continue
            item = obj.to_dict()
            item.update({"spaces": space, "etl_config": etl_conf})
            data.append(item)

        # 计算数量，进行分页
        ret_data["total"] = len(data)
        start, end = (page - 1) * page_size, page * page_size
        ret_data["data"] = data[start:end]
        return ret_data

    @classmethod
    def check_exist_default(cls, spaces: List[Dict], etl_configs: List[str]) -> bool:
        """检测指定条件下是否已经存在默认链路"""
        # 根据使用范围过滤数据
        space_filter_params = Q()
        for space in spaces:
            space_type = space.get("space_type")
            space_id = space.get("space_id")
            if space_type:
                space_filter_params |= Q(space_type=space_type)
            if space_id:
                space_filter_params |= Q(space_id=space_id)
        space_qs = DataPipelineSpace.objects.filter(space_filter_params).filter(is_default=True)
        # 根据使用场景进行过滤
        etl_conf_qs = DataPipelineEtlConfig.objects.filter(etl_config__in=etl_configs, is_default=True)
        # 如果空间或者使用场景下存在相同的默认值，则不允许在设置默认值
        if space_qs.exists() or etl_conf_qs.exists():
            return True

        return False

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_record(
        cls,
        name: str,
        etl_configs: List[str],
        spaces: List[Dict],
        kafka_cluster_id: int,
        transfer_cluster_id: str,
        creator: str,
        chinese_name: Optional[str] = "",
        label: Optional[str] = "",
        influxdb_storage_cluster_id: Optional[int] = None,
        kafka_storage_cluster_id: Optional[int] = None,
        es_storage_cluster_id: Optional[int] = None,
        vm_storage_cluster_id: Optional[int] = None,
        is_enable: Optional[bool] = True,
        is_default: Optional[bool] = False,
        description: Optional[str] = "",
    ):
        """创建数据链路
        :param name: 链路名称
        :param etl_configs: 使用场景
        :param spaces: 允许使用的空间范围
        :param kafka_cluster_id: kafka 消息队列集群 ID
        :param transfer_cluster_id: transfer 集群 ID
        :param creator: 用户名称
        :param chinese_name: 管道中文名称
        :param label: 管道标签
        :param influxdb_storage_cluster_id: influxdb 存储集群 ID
        :param kafka_storage_cluster_id: kafka 存储集群 ID
        :param es_storage_cluster_id: es 存储集群 ID
        :param vm_storage_cluster_id: vm 存储集群 ID
        :param is_enable: 是否启用
        :param is_default: 是否默认集群
        :param description: 管道的描述信息
        """
        # 校验是否可以设置默认
        if is_default and cls.check_exist_default(spaces, etl_configs):
            raise ValueError(_lazy("已经存在默认记录，空间信息: {}, 使用场景: {}").format(json.dumps(spaces), json.dumps(etl_configs)))

        try:
            # 创建管道
            obj_name = cls.objects.create_record(
                name,
                kafka_cluster_id,
                transfer_cluster_id,
                creator,
                chinese_name=chinese_name,
                label=label,
                influxdb_storage_cluster_id=influxdb_storage_cluster_id,
                kafka_storage_cluster_id=kafka_storage_cluster_id,
                es_storage_cluster_id=es_storage_cluster_id,
                vm_storage_cluster_id=vm_storage_cluster_id,
                is_enable=is_enable,
                description=description,
            )

            # 创建使用场景
            DataPipelineEtlConfig.objects.create_record(obj_name, etl_configs, creator, is_default=is_default)

            # 创建空间范围
            DataPipelineSpace.objects.create_record(obj_name, spaces, creator, is_default=is_default)
        except Exception:
            logger.exception("create record failed")
            raise

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def update_record(
        cls,
        name: str,
        updater: str,
        is_enable: Optional[bool] = None,
        is_default: Optional[bool] = None,
        description: Optional[str] = None,
        etl_configs: Optional[List[str]] = None,
        spaces: Optional[List[Dict]] = None,
    ) -> "DataPipeline":
        try:
            obj = cls.objects.get(name=name)
        except cls.DoesNotExist:
            raise ValueError("name: %s not exists", name)
        obj.updater = updater
        update_fields = ["updater"]
        if description is not None:
            obj.description = description
            update_fields.append("description")
        # 更新属性
        if is_enable is False and utils.check_data_pipeline_used(obj.name):
            raise ValueError("name: %s not disabled", name)
        if is_enable is not None:
            obj.is_enable = is_enable
            update_fields.append("is_enable")

        # NOTE: 需要删除已经不属于管道使用的范围或者使用场景
        if etl_configs:
            DataPipelineEtlConfig.objects.filter(data_pipeline_name=name).delete()
            DataPipelineEtlConfig.objects.create_record(
                data_pipeline_name=name, etl_configs=etl_configs, username=updater
            )
        elif is_default is not None:
            etl_configs = list(
                DataPipelineEtlConfig.objects.filter(data_pipeline_name=name, is_default=True).values_list(
                    "etl_config", flat=True
                )
            )
        if spaces:
            DataPipelineSpace.objects.filter(data_pipeline_name=name).delete()
            DataPipelineSpace.objects.create_record(data_pipeline_name=name, spaces=spaces, username=updater)
        elif is_default is not None:
            spaces = list(
                DataPipelineSpace.objects.filter(data_pipeline_name=name, is_default=True).values(
                    "space_type", "space_id"
                )
            )

        # 校验默认集群存在
        if is_default and cls.check_exist_default(spaces, etl_configs):
            logger.error(
                "default pipeline has exist, space: %s, etl_configs: %s", json.dumps(spaces), json.dumps(etl_configs)
            )
            raise ValueError("default pipeline has exist")
        # 更新记录
        obj.save(update_fields=update_fields)
        # 更新默认管道, 设置使用场景和使用范围

        if is_default is not None:
            DataPipelineEtlConfig.objects.update_record(name, etl_configs, updater, is_default=is_default)
            DataPipelineSpace.objects.update_record(name, spaces, updater, is_default=is_default)

        # 组装返回数据
        data = obj.to_dict()
        data.update(
            {
                "spaces": list(
                    DataPipelineSpace.objects.filter(data_pipeline_name=name).values(
                        "space_type", "space_id", "is_default"
                    )
                ),
                "etl_config": list(
                    DataPipelineEtlConfig.objects.filter(data_pipeline_name=name).values("etl_config", "is_default")
                ),
            }
        )

        return data


class DataPipelineEtlConfig(BaseModel):
    """数据管道的场景类型关联"""

    data_pipeline_name = models.CharField("链路管道名称", max_length=64)
    etl_config = models.CharField("允许的场景类型", max_length=32)
    is_default = models.BooleanField("是否为默认", default=False)

    objects = DataPipelineEtlConfigManager()

    class Meta:
        verbose_name = "数据链路和场景类型关系"
        verbose_name_plural = "数据链路和场景类型关系"


class DataPipelineSpace(BaseModel):
    data_pipeline_name = models.CharField("链路管道名称", max_length=64)
    space_type = models.CharField("允许的空间类型", max_length=64)
    space_id = models.CharField(
        "允许的空间ID", max_length=256, null=True, blank=True, help_text="允许的空间 ID, 当允许某一类空间访问时，可以为空"
    )
    is_default = models.BooleanField("是否为默认", default=False)

    objects = DataPipelineSpaceManager()

    class Meta:
        verbose_name = "数据链路和空间关系"
        verbose_name_plural = "数据链路和空间关系"


class DataPipelineDataSource(BaseModel):
    data_pipeline_name = models.CharField("链路管道名称", max_length=64)
    bk_data_id = models.IntegerField("数据源 ID")

    objects = DataPipelineDataSourceManager()

    class Meta:
        unique_together = ("data_pipeline_name", "bk_data_id")
        verbose_name = "数据链路和数据源关系"
        verbose_name_plural = "数据链路和数据源关系"
