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

import abc
import base64
import datetime
import json
import logging
import re
import time
import traceback
from typing import Dict, List, Optional

import arrow
import curator
import elasticsearch
import elasticsearch5
import elasticsearch6
import influxdb
import requests
from bkcrypto.contrib.django.fields import SymmetricTextField
from django.conf import settings
from django.db import models
from django.db.models.fields import DateTimeField
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from pytz import timezone

from bkmonitor.dataflow import auth
from bkmonitor.dataflow.task.cmdblevel import CMDBPrepareAggregateTask
from bkmonitor.dataflow.task.downsample import StatisticTask
from bkmonitor.dataflow.task.filtertime import FilterUnknownTimeTask
from bkmonitor.utils.common_utils import (
    gen_bk_data_rt_id_without_biz_id,
    to_bk_data_rt_id,
)
from bkmonitor.utils.db.fields import JsonField
from bkmonitor.utils.elasticsearch.curator import IndexList
from bkmonitor.utils.time_tools import datetime_str_to_datetime
from core.drf_resource import api
from metadata import config
from metadata.models import constants
from metadata.models.influxdb_cluster import InfluxDBTool
from metadata.utils import consul_tools, es_tools, go_time, influxdb_tools
from metadata.utils.redis_tools import RedisTools

from .constants import ES_ALIAS_EXPIRED_DELAY_DAYS
from .es_snapshot import EsSnapshot, EsSnapshotIndice
from .influxdb_cluster import (
    InfluxDBClusterInfo,
    InfluxDBHostInfo,
    InfluxDBProxyStorage,
)

logger = logging.getLogger("metadata")

ResultTableField = None
ResultTableFieldOption = None
ResultTable = None
EventGroup = None


class ClusterInfo(models.Model):
    """
    集群信息配置
    此处的集群信息，主要是指对于外部使用监控kafka集群或者influxDB-proxy集群的信息
    如果需要看到influxDB-proxy后面的实际集群信息，请看InfluxDBClusterInfo记录
    """

    CONSUL_PREFIX_PATH = "%s/unify-query/data/storage" % config.CONSUL_PATH
    CONSUL_VERSION_PATH = "%s/unify-query/version/storage" % config.CONSUL_PATH

    TYPE_INFLUXDB = "influxdb"
    TYPE_KAFKA = "kafka"
    TYPE_REDIS = "redis"
    TYPE_BKDATA = "bkdata"
    TYPE_ES = "elasticsearch"
    TYPE_ARGUS = "argus"
    TYPE_VM = "victoria_metrics"

    CLUSTER_TYPE_CHOICES = (
        (TYPE_INFLUXDB, "influxDB"),
        (TYPE_KAFKA, "kafka"),
        (TYPE_REDIS, "redis"),
        (TYPE_ES, "elasticsearch"),
        (TYPE_ARGUS, "argus"),
        (TYPE_VM, "victoria_metrics"),
    )

    # 默认注册系统名
    DEFAULT_REGISTERED_SYSTEM = "_default"
    LOG_PLATFORM_REGISTERED_SYSTEM = "log-search-4"

    cluster_id = models.AutoField("集群ID", primary_key=True)
    # 集群中文名，便于管理员维护
    cluster_name = models.CharField("集群名称", max_length=128, unique=True)
    cluster_type = models.CharField("集群类型", max_length=32, db_index=True)
    domain_name = models.CharField("集群域名", max_length=128)
    port = models.IntegerField("端口")
    extranet_domain_name = models.CharField("集群外网域名", max_length=128, null=True, default="")
    extranet_port = models.IntegerField("集群外网端口", null=True, default=0)
    description = models.CharField("集群备注说明信息", max_length=256)
    # 是否默认使用的集群
    # 当用户尝试使用该类型的集群时，且没有指定集群ID，则会优先使用默认集群
    is_default_cluster = models.BooleanField("是否默认集群")
    # 用户名及密码配置
    username = models.CharField("用户名", max_length=64, default="")
    password = SymmetricTextField("密码", max_length=128, default="")
    version = models.CharField("存储集群版本", max_length=64, default=None, null=True)
    # 自定义标签信息，此处存储的内容是格式化数据，供机器读写使用
    custom_option = models.TextField("自定义标签", default="")
    # 供部分http协议连接方案的存储使用，配置可以为http或者https等
    schema = models.CharField("访问协议", max_length=32, default=None, null=True)
    # ssl/tls 校验参数相关
    is_ssl_verify = models.BooleanField("SSL验证是否强验证", default=False)
    ssl_verification_mode = models.CharField("CA 校验模式", max_length=16, null=True, default="none")
    ssl_certificate_authorities = models.TextField("CA 内容", null=True, default="")
    ssl_certificate = models.TextField("SSL/TLS 证书内容", null=True, default="")
    ssl_certificate_key = models.TextField("SSL/TLS 证书私钥内容", null=True, default="")
    ssl_insecure_skip_verify = models.BooleanField("是否跳过服务器校验", default=False)

    # 描述该存储集群被何系统使用
    registered_system = models.CharField("注册来源系统", default=DEFAULT_REGISTERED_SYSTEM, max_length=128)

    # GSE注册相关
    # 是否需要往GSE注册
    is_register_to_gse = models.BooleanField(verbose_name="是否需要往GSE注册", default=False)
    gse_stream_to_id = models.IntegerField(verbose_name="GSE接收端配置ID", default=-1)

    # 用于标识用途标签
    label = models.CharField("用途标签", max_length=32, null=True, default="")
    default_settings = JsonField("集群的默认配置", default={}, null=True)

    # 创建和修改信息
    creator = models.CharField("创建者", default="system", max_length=255)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32, default="system")
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "集群配置信息"
        verbose_name_plural = "集群配置信息"

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
    def refresh_consul_storage_config(cls):
        """
        刷新查询模块的table consul配置
        :return: None
        """

        hash_consul = consul_tools.HashConsul()

        # 1. 获取需要刷新的信息列表
        info_list = cls.objects.all()

        total_count = info_list.count()
        logger.debug("total find->[{}] es storage info to refresh".format(total_count))

        # 2. 构建需要刷新的字典信息
        refresh_dict = {}
        for storage_info in info_list:
            refresh_dict[storage_info.cluster_id] = storage_info

        # 3. 遍历所有的字典信息并写入至consul
        for cluster_id, storage_info in list(refresh_dict.items()):
            consul_path = "/".join([cls.CONSUL_PREFIX_PATH, str(cluster_id)])

            hash_consul.put(
                key=consul_path,
                value={
                    "address": "http://{}:{}".format(storage_info.domain_name, storage_info.port),
                    "username": storage_info.username,
                    "password": storage_info.password,
                    "type": storage_info.cluster_type,
                },
            )
            logger.debug("consul path->[{}] is refresh with value->[{}] success.".format(consul_path, refresh_dict))

        hash_consul.put(key=cls.CONSUL_VERSION_PATH, value={"time": time.time()})

        logger.info("all es table info is refresh to consul success count->[%s]." % total_count)

    def base64_with_prefix(self, content: str) -> str:
        """编码，并添加上前缀"""
        # 如果为空，则直接返回
        if not content:
            return content
        # 添加的前缀
        prefix = "base64://"
        try:
            _content = base64.b64encode(content.encode("utf-8"))
            _content_with_prefix = prefix + str(_content, "utf-8")
            return _content_with_prefix
        except Exception as err:
            logger.error("convert cert error, %s", err)
            return ""

    @property
    def consul_config(self):
        """
        返回consul配置，字典
        :return: {
            "cluster_config": {
                "domain_name": self.mq_cluster.domain_name,
                "port": self.mq_cluster.port,
            },
            "cluster_type": self.mq_cluster.cluster_type
        }
        """

        return {
            "cluster_config": {
                "domain_name": self.domain_name,
                "port": self.port,
                "extranet_domain_name": self.extranet_domain_name,
                "extranet_port": self.extranet_port,
                "schema": self.schema,
                "is_ssl_verify": self.is_ssl_verify,
                "ssl_verification_mode": self.ssl_verification_mode,
                "ssl_insecure_skip_verify": self.ssl_insecure_skip_verify,
                "ssl_certificate_authorities": self.base64_with_prefix(self.ssl_certificate_authorities),
                "ssl_certificate": self.base64_with_prefix(self.ssl_certificate),
                "ssl_certificate_key": self.base64_with_prefix(self.ssl_certificate_key),
                "raw_ssl_certificate_authorities": self.ssl_certificate_authorities,
                "raw_ssl_certificate": self.ssl_certificate,
                "raw_ssl_certificate_key": self.ssl_certificate_key,
                "cluster_id": self.cluster_id,
                "cluster_name": self.cluster_name,
                "version": self.version,
                "custom_option": self.custom_option,
                "registered_system": self.registered_system,
                "creator": self.creator,
                "create_time": arrow.get(self.create_time).timestamp,
                "last_modify_user": self.last_modify_user,
                "last_modify_time": arrow.get(self.last_modify_time).timestamp,
                "is_default_cluster": self.is_default_cluster,
            },
            "cluster_type": self.cluster_type,
            "auth_info": {"password": self.password, "username": self.username},
        }

    @property
    def cluster_detail(self):
        consul_config = self.consul_config
        detail = consul_config["cluster_config"]
        detail.update(
            {
                "cluster_type": consul_config["cluster_type"],
                "auth_info": consul_config["auth_info"],
                "label": self.label,
                "default_settings": self.default_settings,
            }
        )
        return detail

    def cluster_init(self):
        """
        集群初始化（目前主要针对ES集群处理，后续如果其他集群也需要的话，可以写成集成的方式）
        :return:
        """
        # 如果是es集群，那么需要禁用write_开头的索引自动创建
        if self.cluster_type == self.TYPE_ES:
            try:
                disable_start_with_write = "-write_*"
                client = es_tools.get_client(self.cluster_id)
                cluster_settings = client.cluster.get_settings()
                auto_create_index = (
                    cluster_settings.get("persistent", {}).get("action", {}).get("auto_create_index", "*")
                )
                if auto_create_index == "false":
                    return

                auto_create_index = "*" if auto_create_index == "true" else auto_create_index
                # 如果本身没有禁用自动创建索引配置，并且也没有禁用write开头的索引创建，那么则增加上配置
                if disable_start_with_write not in auto_create_index.split(","):
                    new_auto_create_index = ",".join([disable_start_with_write, auto_create_index])
                    ret = client.cluster.put_settings(
                        body={
                            "persistent": {"action": {"auto_create_index": new_auto_create_index}},
                        }
                    )
                    logger.info("cluster({}) init success, ret({})".format(self.cluster_name, ret))
            except Exception as e:  # noqa
                logger.error("cluster({}) init error, {}".format(self.cluster_name, e))

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_cluster(
        cls,
        cluster_name,
        cluster_type,
        domain_name,
        port,
        registered_system,
        operator,
        description="",
        username="",
        password="",
        version="",
        custom_option="",
        schema="",
        is_ssl_verify=False,
        label="",
        default_settings=None,
        ssl_verification_mode: Optional[str] = "",
        ssl_certificate_authorities: Optional[str] = "",
        ssl_certificate: Optional[str] = "",
        ssl_certificate_key: Optional[str] = "",
        ssl_insecure_skip_verify: Optional[bool] = False,
        extranet_domain_name: Optional[str] = "",
        extranet_port: Optional[int] = 0,
    ):
        """
        创建一个存储集群信息
        :param cluster_name: 集群名
        :param cluster_type: 集群类型
        :param domain_name: 集群域名，也可以提供集群IP
        :param port: 集群端口
        :param operator: 创建者
        :param description: 集群描述内容，可以为空
        :param username: 用户名，用于身份验证（如果有）
        :param password: 密码，用于身份验证（如果有）
        :param version: 集群版本信息
        :param custom_option: 自定义标签
        :param schema: 通信协议，可以提供https或http的差异
        :param is_ssl_verify: 是否需要强制验证SSL
        :param registered_system: 注册来源系统
        :param label: 集群的用途标签
        :param default_settings: 默认集群配置
        :param ssl_verification_mode: CA 校验模式
        :param ssl_certificate_authorities: CA 证书路径
        :param ssl_certificate: ssl/tls 证书
        :param ssl_certificate_key: ssl/tls 证书私钥
        :param ssl_insecure_skip_verify: 是否跳过服务端校验
        :param extranet_domain_name: 外网域名
        :param extranet_port: 外网端口
        :return: clusterInfo object
        """

        # 1. 判断请求的数据是否有冲突
        # 基本数据校验
        if cls.objects.filter(cluster_name=cluster_name).exists():
            logger.error(
                "reg_system->[{}] try to add cluster with name->[{}] which is already exists, nothing "
                "will do".format(registered_system, cluster_name)
            )
            raise ValueError(_("集群名【{}】与已有集群冲突，请确认后重试").format(cluster_name))

        if cluster_type not in (cls.TYPE_INFLUXDB, cls.TYPE_ES, cls.TYPE_KAFKA, cls.TYPE_REDIS, cls.TYPE_ARGUS):
            logger.error(
                "reg_system->[{}] try to add cluster type->[{}] but is not at CLUSTER_TYPE_CHOICES, nothing "
                "will do".format(registered_system, cluster_type)
            )
            raise ValueError(_("存储集群【{}】暂不支持，请确认后重试").format(cluster_type))

        # 判断集群信息是否有存在冲突的
        if cls.objects.filter(domain_name=domain_name, port=port, username=username).exists():
            logger.error(
                "reg_system->[{}] try to add cluster->[{}] with domain->[{}] port->[{}] username->[{}] "
                "pass->[{}] which already has the same cluster config , nothing will do.".format(
                    registered_system, cluster_type, domain_name, port, username, password
                )
            )
            raise ValueError(_("存在同样配置集群，请确认后重试"))

        # 2. 创建新的逻辑
        new_cluster = cls.objects.create(
            cluster_name=cluster_name,
            cluster_type=cluster_type,
            domain_name=domain_name,
            port=port,
            extranet_domain_name=extranet_domain_name,
            extranet_port=extranet_port,
            registered_system=registered_system,
            creator=operator,
            last_modify_user=operator,
            description=description,
            username=username,
            password=password,
            version=version,
            custom_option=custom_option,
            schema=schema,
            is_ssl_verify=is_ssl_verify,
            # 新添加的，不可以为默认集群，触发运维通过admin修改
            is_default_cluster=False,
            label=label,
            default_settings=default_settings or {},
            ssl_verification_mode=ssl_verification_mode or "",
            ssl_certificate_authorities=ssl_certificate_authorities or "",
            ssl_certificate=ssl_certificate or "",
            ssl_certificate_key=ssl_certificate_key or "",
            ssl_insecure_skip_verify=ssl_insecure_skip_verify,
        )
        logger.info(
            "reg_system->[{}] created new cluster->[{}] type->[{}]".format(
                registered_system, new_cluster.cluster_id, cluster_type
            )
        )
        new_cluster.cluster_init()

        return new_cluster

    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify(
        self,
        operator,
        description=None,
        username=None,
        password=None,
        custom_option=None,
        schema=None,
        is_ssl_verify=None,
        version=None,
        label="",
        default_settings=None,
        ssl_verification_mode: Optional[str] = None,
        ssl_certificate_authorities: Optional[str] = None,
        ssl_certificate: Optional[str] = None,
        ssl_certificate_key: Optional[str] = None,
        ssl_insecure_skip_verify: Optional[bool] = None,
        extranet_domain_name: Optional[str] = None,
        extranet_port: Optional[int] = None,
    ):
        """
        修改存储集群信息
        :param operator: 操作者
        :param description: 描述信息
        :param username: 用户名
        :param password: 密码
        :param custom_option: 自定义标签信息
        :param schema: 通信协议
        :param is_ssl_verify: 是否需要强制验证SSL
        :param label: 集群用途标签
        :param default_settings: 默认集群配置
        :param ssl_verification_mode: CA 校验模式
        :param ssl_certificate_authorities: CA 证书路径
        :param ssl_certificate: ssl/tls 证书
        :param ssl_certificate_key: ssl/tls 证书私钥
        :param ssl_insecure_skip_verify: 是否跳过服务端校验
        :param extranet_domain_name: 外网域名
        :param extranet_port: 外网端口
        :return: True | raise Exception
        """
        args = {
            "description": description,
            "username": username,
            "password": password,
            "custom_option": custom_option,
            "schema": schema,
            "is_ssl_verify": is_ssl_verify,
            "label": label,
            "default_settings": default_settings,
            "version": version,
            "ssl_verification_mode": ssl_verification_mode,
            "ssl_certificate_authorities": ssl_certificate_authorities,
            "ssl_certificate": ssl_certificate,
            "ssl_certificate_key": ssl_certificate_key,
            "ssl_insecure_skip_verify": ssl_insecure_skip_verify,
            "extranet_domain_name": extranet_domain_name,
            "extranet_port": extranet_port,
        }

        # 遍历更新，降低重复代码
        for attribute_name, value in list(args.items()):
            if value is not None:
                setattr(self, attribute_name, value)
                # 由于已经有更新了，所以需要更新最后更新者
                self.last_modify_user = operator
                logger.info(
                    "cluster->[{}] attribute->[{}] is set to->[{}] by->[{}]".format(
                        self.cluster_name, attribute_name, value, operator
                    )
                )

        self.save()
        logger.info("cluster->[{}] update success.".format(self.cluster_name))
        return True

    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete(self, *args, **kwargs):
        if self.is_default_cluster:
            raise ValueError(_("默认集群不能删除"))

        real_storage = ResultTable.REAL_STORAGE_DICT[self.cluster_type]
        storage_table_ids = real_storage.objects.filter(storage_cluster_id=self.cluster_id).values_list(
            "table_id", flat=True
        )
        # 检测是否有未关闭的结果表
        enable_rts = ResultTable.objects.filter(
            table_id__in=storage_table_ids, is_enable=True, is_deleted=False
        ).values_list("table_id", flat=True)

        if enable_rts:
            logger.info(
                "cluster->[{}] has not closed result table [{}]".format(self.cluster_name, ",".join(enable_rts))
            )
            raise ValueError(_("存在未关闭的结果表 {}").format(','.join(enable_rts)))

        super(ClusterInfo, self).delete(*args, **kwargs)

        logger.info(
            "cluster->[{}] cluster_type->[{}] has deleted by [{}]".format(
                self.cluster_name, self.cluster_type, self.registered_system
            )
        )


class KafkaTopicInfo(models.Model):
    """数据源对应的Kafka队列配置"""

    bk_data_id = models.IntegerField("数据源ID", unique=True)
    topic = models.CharField("kafka topic", max_length=128)
    partition = models.IntegerField("分区数量")
    # transfer 写入配置
    batch_size = models.IntegerField("批量写入的大小", default=None, null=True)
    flush_interval = models.CharField("写入间隔", max_length=16, default=None, null=True)
    consume_rate = models.IntegerField("消费速率", default=None, null=True)

    class Meta:
        verbose_name = "Kafka消息队列配置"
        verbose_name_plural = "Kafka消息队列配置表"

    @classmethod
    def create_info(cls, bk_data_id, topic=None, partition=1, batch_size=None, flush_interval=None, consume_rate=None):
        """
        创建一个新的Topic信息
        :param bk_data_id: 数据源ID
        :param topic: topic默认与data_id一致，如果有提供，使用提供的topic
        :param partition: 默认分区为1，如果有提供，则使用提供的分区值
        :param batch_size: 批量写入的大小
        :param flush_interval: 刷新间隔
        :param consume_rate: 消费速率
        :return: KafkaTopicInfo | raise Exception
        """
        # 1. 判断是否已经存在该data_id的配置
        if cls.objects.filter(bk_data_id=bk_data_id).exists():
            logger.error(
                "try to create kafka topic for data_id->[%s], but which is already exists, "
                "something go wrong?" % bk_data_id
            )
            raise ValueError(_("数据源已经配置，请确认"))

        # 2. 创建新的记录
        info = cls.objects.create(
            bk_data_id=bk_data_id,
            # 如果topic没有指定，则设定为该data_id同名
            # TOPIC的生成规范，可以参考DataSource.gse_config注释
            topic=topic if topic is not None else "{}{}0".format(config.KAFKA_TOPIC_PREFIX, bk_data_id),
            partition=partition,
            batch_size=batch_size,
            flush_interval=flush_interval,
            consume_rate=consume_rate,
        )
        logger.info(
            "new kafka topic is set for data_id->[%s] topic->[%s] partition->[%s]"
            % (info.bk_data_id, info.topic, info.partition)
        )

        # 3. 返回新的实例
        return info


class StorageResultTable(object):
    """实际结果表基类，提供公共方法的模板"""

    STORAGE_TYPE = None
    UPGRADE_FIELD_CONFIG = ()

    # JSON 类型的字段列表
    JSON_FIELDS = ()

    # 对应ResultTable的table_id
    table_id = None
    storage_cluster_id = None

    @classmethod
    @abc.abstractmethod
    def create_table(cls, table_id, is_sync_db=False, **kwargs):
        """实际创建结果表"""
        # 注意在创建结果表的时候，需要注意
        # 1. 创建当前结果表的DB信息记录
        # 2. 创建实际结果表，带上所有的字段
        pass

    @abc.abstractmethod
    def get_client(self):
        """获取该结果表的客户端句柄"""
        pass

    @abc.abstractmethod
    def add_field(self, field):
        """增加一个新的字段"""

    @abc.abstractproperty
    def consul_config(self):
        """返回一个实际存储的consul配置"""
        pass

    def update_storage(self, **kwargs):
        """更新存储配置"""
        # 遍历获取所有可以更新的字段，逐一更新
        for field_name in self.UPGRADE_FIELD_CONFIG:
            # 尝试获取配置
            upgrade_config = kwargs.get(field_name, None)

            if upgrade_config is None:
                logger.info(
                    "table_id->[{}] try to upgrade storage->[{}] config->[{}] but is not exists, "
                    "nothing will do.".format(self.table_id, self.STORAGE_TYPE, field_name)
                )
                continue

            # 判断写入的内容是否字典，如果是，需要json dumps一波
            if type(upgrade_config) in (dict, list) and field_name not in self.JSON_FIELDS:
                setattr(self, field_name, json.dumps(upgrade_config))

            else:
                setattr(self, field_name, upgrade_config)

            logger.info(
                "table_id->[{}] storage->[{}] has upgrade attribute->[{}] to->[{}]".format(
                    self.table_id, self.STORAGE_TYPE, field_name, upgrade_config
                )
            )

        self.save()
        logger.info("table->[{}] storage->[{}] upgrade operation success.".format(self.table_id, self.STORAGE_TYPE))

        return True

    @property
    def storage_cluster(self):
        """返回数据源的消息队列类型"""
        # 这个配置应该是很少变化的，所以考虑增加缓存
        if getattr(self, "_cluster", None) is None:
            self._cluster = ClusterInfo.objects.get(cluster_id=self.storage_cluster_id)

        return self._cluster


class InfluxDBStorage(models.Model, StorageResultTable, InfluxDBTool):
    """TSDB物理表配置"""

    # TODO: consul 中 router 的信息，待 redis 数据稳定后，可以删除
    CONSUL_CONFIG_CLUSTER_PATH = "%s/influxdb_info/router" % config.CONSUL_PATH

    STORAGE_TYPE = ClusterInfo.TYPE_INFLUXDB
    UPGRADE_FIELD_CONFIG = ("source_duration_time",)

    # 对应ResultTable的table_id
    table_id = models.CharField("结果表名", max_length=128, primary_key=True)
    # 对应StorageCluster记录ID
    # 该字段配置，供监控存储外部使用
    storage_cluster_id = models.IntegerField("存储集群")
    real_table_name = models.CharField("实际存储表名", max_length=128)
    database = models.CharField("数据库名", max_length=128)
    # 字段格式应该符合influxDB的格式
    source_duration_time = models.CharField("原始数据保留时间", max_length=32)
    # 降样后的表名
    down_sample_table = models.CharField("降样结果表名", blank=True, max_length=128)
    down_sample_gap = models.CharField("降样聚合区间", blank=True, max_length=32)
    # 字段格式应该符合influxDB的格式
    down_sample_duration_time = models.CharField("降样数据的保存时间", blank=True, max_length=32)
    # 实际存储（influxdb-proxy后）的存储集群名字
    # 该字段配置，供influxdb-proxy使用
    # 默认对于新建的结果表，如果在没有指定的情况下，使用默认集群
    proxy_cluster_name = models.CharField("实际存储集群名字", default="default", max_length=128)
    use_default_rp = models.BooleanField("是否使用默认RP配置", default=True)
    enable_refresh_rp = models.BooleanField("是否周期刷新rp", default=True)
    partition_tag = models.CharField("tag分组列表", blank=True, default="", max_length=128)
    vm_table_id = models.CharField(
        "VM 结果表 ID", blank=True, default="", max_length=128, help_text="此字段废弃，vm 结果表 ID 可以通过 AccessVMRecord 获取"
    )
    influxdb_proxy_storage_id = models.IntegerField(
        "influxdb proxy 和 存储的关联关系 ID",
        blank=True,
        null=True,
        help_text="设置influxdb proxy 和 后端存储集群的关联关系记录 ID, 用以查询结果表使用的 proxy 和后端存储",
    )

    class Meta:
        # 实际数据库存储表信息不可重复
        unique_together = ("real_table_name", "database")
        verbose_name = "TSDB物理表配置"
        verbose_name_plural = "TSDB物理表配置"

    @classmethod
    def export_data(cls):
        items = cls.objects.all()
        data = list(
            items.values(
                "table_id",
                "storage_cluster_id",
                "real_table_name",
                "database",
                "source_duration_time",
                "down_sample_table",
                "down_sample_gap",
                "down_sample_duration_time",
                "proxy_cluster_name",
                "use_default_rp",
                "partition_tag",
                "influxdb_proxy_storage_id",
            )
        )
        return data

    @classmethod
    def import_data(cls, data):
        items = data
        delete_list = []
        for info in cls.objects.all():
            exist = False
            for item in items:
                if (item["real_table_name"] == info.real_table_name) and (item["database"] == info.database):
                    exist = True
            if not exist:
                delete_list.append(info)

        for info in delete_list:
            data = info.__dict__
            info.delete()
            logger.info("delete route info:{}".format(data))

        for item in items:
            # info = InfluxDBTagInfo(**item)
            obj, created = cls.objects.update_or_create(
                real_table_name=item["real_table_name"],
                database=item["database"],
                defaults=item,
            )
            if created:
                logger.info("create new route info:{}".format(str(item)))
            else:
                logger.info("update route info to:{}".format(str(item)))

    @property
    def influxdb_proxy_storage(self) -> InfluxDBProxyStorage:
        if (
            getattr(self, "_influxdb_proxy_storage", None)
            and self._influxdb_proxy_storage.id == self.influxdb_proxy_storage_id
        ):
            return self._influxdb_proxy_storage

        # 查询记录
        try:
            self._influxdb_proxy_storage = InfluxDBProxyStorage.objects.get(id=self.influxdb_proxy_storage_id)
            return self._influxdb_proxy_storage
        except InfluxDBProxyStorage.DoesNotExist:
            raise ValueError("influxdb proxy storage: %s does not exist", self.influxdb_proxy_storage_id)

    def get_influxdb_storage(
        self,
        influxdb_proxy_storage_id: Optional[int] = None,
        proxy_cluster_name: Optional[str] = None,
        storage_cluster_id: Optional[int] = None,
    ) -> InfluxDBProxyStorage:
        """获取 proxy 集群和存储集群名称

        优先以 influxdb_proxy_storage_id 数据为准
        1. 如果 influxdb_proxy_storage_id 存在，则查询到对应 proxy_cluster_name 和 storage_cluster_id
        2. 如果 proxy_cluster_name 和 storage_cluster_id 都存在，则需要校验是否存在，如果不存在，则记录并使用默认值
        3. 如果 proxy_cluster_name 或者 storage_cluster_id 只有一个存在时，则使用默认查询到的第一个记录
        """
        # 满足条件 1
        if influxdb_proxy_storage_id is not None:
            try:
                return InfluxDBProxyStorage.objects.get(id=influxdb_proxy_storage_id)
            except InfluxDBProxyStorage.DoesNotExist:
                raise ValueError("influxdb proxy storage: %s does not exist", influxdb_proxy_storage_id)
        # 满足条件 2
        if proxy_cluster_name and storage_cluster_id:
            try:
                return InfluxDBProxyStorage.objects.get(
                    proxy_cluster_id=storage_cluster_id, instance_cluster_name=proxy_cluster_name
                )
            except InfluxDBProxyStorage.DoesNotExist:
                err_msg = f"influxdb proxy storage: ({storage_cluster_id}, {proxy_cluster_name}) does not exist"
                # 记录下日志，方便追踪
                logger.error(err_msg)
                raise ValueError(err_msg)
        # 满足条件 3
        # 去掉这里的[default]限制，因为 influxdb proxy 可能对应多个 influxdb 集群
        else:
            if storage_cluster_id:
                logger.info("query influxdb proxy storage by proxy cluster id: %s", storage_cluster_id)
                record = InfluxDBProxyStorage.objects.filter(proxy_cluster_id=storage_cluster_id).first()
            elif proxy_cluster_name:
                logger.info("query influxdb proxy storage by storage cluster name: %s", proxy_cluster_name)
                record = InfluxDBProxyStorage.objects.filter(instance_cluster_name=proxy_cluster_name).first()
            else:
                logger.info("query influxdb proxy storage default record")
                record = InfluxDBProxyStorage.objects.filter(is_default=True).first()
            if not record:
                raise ValueError("influxdb proxy storage has not record")
            return record

    @property
    def storage_cluster(self):
        """返回数据源的消息队列类型"""
        # 这个配置应该是很少变化的，所以考虑增加缓存
        if getattr(self, "_cluster", None) is None:
            self._cluster = ClusterInfo.objects.get(cluster_id=self.influxdb_proxy_storage.proxy_cluster_id)

        return self._cluster

    @classmethod
    def create_table(
        cls,
        table_id,
        is_sync_db=True,
        storage_cluster_id=None,
        database=None,
        real_table_name=None,
        source_duration_time="30d",
        proxy_cluster_name=None,
        influxdb_proxy_storage_id=None,
        **kwargs,
    ):
        """
        创建一个实际的结果表
        :param table_id: 结果表ID
        :param is_sync_db: 是否将创建同步到DB
        :param storage_cluster_id: 数据库集群ID，如果没有指定，则直接使用默认集群
        :param database: 数据库名，如果未None，则使用table_id.split['.'][0]
        :param real_table_name: 实际的结果表名，如果为None, 则使用table_id.split('.')[1]
        :param source_duration_time: 源数据保留的时间，默认是30d
        :param proxy_cluster_name: 对于influxdb-proxy，这个结果表需要路由至哪个集群的配置
        :param influxdb_proxy_storage_id: 添加 influxdb-proxy 和 后端存储的映射 ID
        :param kwargs: 其他创建的参数
        :return: storage object
        """
        # 获取存储的信息，用于后续的校验
        influxdb_proxy_storage = cls().get_influxdb_storage(
            influxdb_proxy_storage_id, proxy_cluster_name, storage_cluster_id
        )
        influxdb_proxy_storage_id, storage_cluster_id, proxy_cluster_name = (
            influxdb_proxy_storage.id,
            influxdb_proxy_storage.proxy_cluster_id,
            influxdb_proxy_storage.instance_cluster_name,
        )
        # 校验后端是否存在
        if not InfluxDBClusterInfo.objects.filter(cluster_name=proxy_cluster_name).exists():
            # 如果调入此处，表示指定的proxy并没有对应的任何机器
            logger.error(
                "proxy_cluster->[%s] has no config, maybe something go wrong?Nothing will do." % proxy_cluster_name
            )
            raise ValueError(_("请求集群[%s]不存在，请确认后重试") % proxy_cluster_name)

        # 如果未有指定对应的结果表及数据库，则从table_id中分割获取
        except_database, except_table_name = table_id.split(".")
        if database is None:
            database = except_database

        if real_table_name is None:
            real_table_name = except_table_name

        # InfluxDB不需要实际创建结果表，只需要创建一条DB记录即可
        new_storage = cls.objects.create(
            table_id=table_id,
            storage_cluster_id=storage_cluster_id,
            database=database,
            real_table_name=real_table_name,
            source_duration_time=source_duration_time,
            proxy_cluster_name=proxy_cluster_name,
            influxdb_proxy_storage_id=influxdb_proxy_storage_id,
            **kwargs,
        )
        logger.info("result_table->[%s] now has create influxDB storage." % new_storage.table_id)

        if is_sync_db:
            new_storage.sync_db()

        # 刷新一次结果表的路由信息至consul中
        # 由于是创建结果表，必须强行刷新到consul配置中
        new_storage.refresh_consul_cluster_config(is_version_refresh=True)

        logger.info("result_table->[%s] all database create is done." % new_storage.table_id)
        return new_storage

    @property
    def consul_config(self):
        consul_config = {
            "storage_config": {
                "real_table_name": self.real_table_name,
                "database": self.database,
                "retention_policy_name": self.rp_name,
            }
        }
        # 添加集群信息
        consul_config.update(self.storage_cluster.consul_config)

        # 将存储的修改时间去掉，防止MD5命中失败
        consul_config["cluster_config"].pop("last_modify_time")
        consul_config["cluster_config"]["instance_cluster_name"] = self.influxdb_proxy_storage.instance_cluster_name

        return consul_config

    def push_redis_data(self, is_publish: bool = True):
        """
        路由存储关系同步写入到 redis 里面
        :return:
        """
        # 通过 AccessVMRecord 获取结果表 ID
        # NOTE: 需要观察 db 的负载
        from metadata.models.vm.record import AccessVMRecord

        # NOTE: 现阶段先兼容获取 VM，后续 tsdb 路由，不包含 vm 相关
        vm_table_id = ""
        try:
            vm_obj = AccessVMRecord.objects.get(result_table_id=self.table_id)
            vm_table_id = vm_obj.vm_result_table_id
        except AccessVMRecord.DoesNotExist:
            logger.warning("table_id: %s not access vm", self.table_id)

        influxdb_proxy_storage = self.influxdb_proxy_storage
        val = {
            "storageID": str(influxdb_proxy_storage.proxy_cluster_id),
            "clusterName": influxdb_proxy_storage.instance_cluster_name,
            "tagsKey": self.partition_tag != "" and self.partition_tag.split(",") or [],
            "db": self.database,
            "vm_rt": vm_table_id,
            "measurement": self.real_table_name,
            "retention_policies": {
                "autogen": {
                    "is_default": True,
                    "resolution": 0,
                },
            },
        }
        self.push_to_redis(constants.INFLUXDB_PROXY_STORAGE_ROUTER_KEY, self.table_id, json.dumps(val), is_publish)

    @property
    def consul_cluster_path(self):
        return "/".join([self.CONSUL_CONFIG_CLUSTER_PATH, self.database, self.real_table_name])

    @property
    def consul_cluster_config(self):
        config = {"cluster": self.influxdb_proxy_storage.instance_cluster_name}

        if self.partition_tag != "":
            partition_tags = self.partition_tag.split(",")
            config["partition_tag"] = partition_tags

        return config

    @property
    def rp_name(self):
        """该结果表的rp名字"""
        if self.use_default_rp:
            return ""

        return "bkmonitor_rp_{}".format(self.table_id)

    def create_database(self):
        """
        创建一个配置记录对应的数据库内容，包括
        1. 数据库的创建
        2. 数据库的downsampling
        未来可以考虑在此增加CQ，保留粗粒度数据
        :return: True | raise Exception
        """
        # NOTE: 针对 `victoria_metrics` 类型集群，暂时不支持创建 DB API, 需要跳过
        if self.storage_cluster.cluster_type in constants.IGNORED_STORAGE_CLUSTER_TYPES:
            logging.info(
                "cluster: %s is victoria_metrics type, not supported create database api",
                self.storage_cluster.cluster_id,
            )
            return True
        # 1. 数据库的创建
        result = requests.post(
            url="http://{}:{}/create_database".format(self.storage_cluster.domain_name, self.storage_cluster.port),
            params={
                # 语句是供非表路由的proxy使用
                "q": 'CREATE DATABASE "%s"' % self.database,
                # cluster及DB名是供表路由proxy使用
                "db": self.database,
                "cluster": self.influxdb_proxy_storage.instance_cluster_name,
            },
            headers={"Content-type": "application/json"},
        )

        # 判断数据库创建是否正常
        if result.status_code >= 300:
            logger.error(
                "failed to create database->[%s] for status->[%s] content->[%s]"
                % (self.database, result.status_code, result.content)
            )
            raise ValueError(_("创建数据库[%s]失败，请联系管理员") % self.database)

        logger.info(
            "database->[{}] is create on host->[{}:{}]".format(
                self.database, self.storage_cluster.domain_name, self.storage_cluster.port
            )
        )
        return True

    def create_rp(self, host_info, name=None, is_update=False):
        """
        创建一个数据库的RP
        :param host_info: 需要创建RP的集群信息 InfluxDBHostInfo
        :param name: RP 名称
        :param is_update: 是否更新rp
        :return: True | raise Exception
        """
        # 判断是否存在这个主机在这个集群中的配置
        proxy_cluster_name = self.influxdb_proxy_storage.instance_cluster_name
        if not InfluxDBClusterInfo.objects.filter(
            cluster_name=proxy_cluster_name, host_name=host_info.host_name
        ).exists():
            logger.error(
                "cluster_info->[%s] is not same as storage cluster_id->[%s]"
                % (host_info.cluster_name, proxy_cluster_name)
            )
            raise ValueError(_("创建集群信息非结果表配置，请确认"))

        client = influxdb.client.InfluxDBClient(host=host_info.domain_name, port=host_info.port)

        rp_config = {
            "name": self.rp_name if name is None else name,
            "duration": self.source_duration_time,
            "database": self.database,
            "default": False,
            "replication": "1",
        }

        # 2. 数据库的配置实施
        if is_update:
            client.alter_retention_policy(**rp_config)
        else:
            client.create_retention_policy(**rp_config)
        logger.info(
            "database->[{}] now has rp duration->[{}] on host->[{}] port->[{}] host_name->[{}]".format(
                self.database, self.source_duration_time, host_info.domain_name, host_info.port, host_info.host_name
            )
        )

        return True

    def ensure_rp(self):
        """
        确保数据库存在该存储的独立RP策略
        :return: True
        """
        # 判断是否使用独立的策略，否则不需要配置
        if self.use_default_rp:
            logger.info("table->[{}] use default rp, nothing will refresh for it.".format(self.table_id))
            return True

        if not self.enable_refresh_rp:
            logger.info("table->[{}] disabled refresh rp, nothing will refresh for it.".format(self.table_id))
            return True

        # 否则，需要在相关的所有机器上，遍历判断RP是否正确配置了
        cluster_list = InfluxDBClusterInfo.objects.filter(
            cluster_name=self.influxdb_proxy_storage.instance_cluster_name
        )
        for cluster_info in cluster_list:
            # 获取当次集群机器的信息
            host_info = InfluxDBHostInfo.objects.get(host_name=cluster_info.host_name)

            # 1. 判断数据库是否存在RP
            client = influxdb.client.InfluxDBClient(
                host=host_info.domain_name,
                port=host_info.port,
            )

            # 如果用户名和密码有配置，需要配置生效使用
            if host_info.username or host_info.password:
                client.switch_user(username=host_info.username, password=host_info.password)
                logger.debug("host->[{}] is set with username and password.".format(host_info.domain_name))

            rp_result = client.get_list_retention_policies(database=self.database)

            # 判断这个rp是否正确配置了
            for rp_info in rp_result:
                duration = rp_info.get("duration", "")
                name = rp_info.get("name", "")

                if name != self.rp_name:
                    continue

                # 判断duration是否一致
                if go_time.parse_duration(duration) == go_time.parse_duration(self.source_duration_time):
                    logger.info(
                        "table->[{}] rp->[{} | {}] check fine on host->[{}]".format(
                            self.table_id, self.rp_name, self.source_duration_time, host_info.domain_name
                        )
                    )
                    # 可以直接找下一个机器了
                    break

                # 否则此处发现rp配置不一致，需要修复
                # 修复前根据新的duration判断shard的长度，并修改为合适的shard
                try:
                    shard_group_duration = InfluxDBHostInfo.judge_shard()
                except ValueError as e:
                    logger.error(
                        "table->[{}] rp->[{} | {}] is updated on host->[{}] failed: [{}]".format(
                            self.table_id, self.rp_name, self.source_duration_time, host_info.domain_name, e
                        )
                    )
                    break
                client.alter_retention_policy(
                    name=self.rp_name,
                    database=self.database,
                    duration=self.source_duration_time,
                    shard_duration=shard_group_duration,
                )
                logger.info(
                    "table->[{}] rp->[{} | {} | {}] is updated on host->[{}]".format(
                        self.table_id,
                        self.rp_name,
                        self.source_duration_time,
                        shard_group_duration,
                        host_info.domain_name,
                    )
                )
                break
            # 如果没有找到, 那么需要创建一个RP
            else:
                # 创建前根据新的duration判断shard的长度，并修改为合适的shard
                try:
                    shard_group_duration = InfluxDBHostInfo.judge_shard()
                except ValueError as e:
                    logger.error(
                        "table->[{}] rp->[{} | {}] is create on host->[{}] failed: [{}]".format(
                            self.table_id, self.rp_name, self.source_duration_time, host_info.domain_name, e
                        )
                    )
                    break
                client.create_retention_policy(
                    name=self.rp_name,
                    database=self.database,
                    duration=self.source_duration_time,
                    replication=1,
                    # 创建时不传shard_duration的值，使用create_retention_policy方法的默认值shard_duration="0s"，
                    # influxdb创建RP的时候如果不写 shard duration 或者令 shard duration 0s
                    # influxdb会自动根据duration创建合理shard长度的RP
                    # shard_duration="7d",
                    shard_duration=shard_group_duration,
                    default=False,
                )
                logger.info(
                    "table->[{}] rp->[{} | {} | {}] is create on host->[{}]".format(
                        self.table_id,
                        self.rp_name,
                        self.source_duration_time,
                        shard_group_duration,
                        host_info.domain_name,
                    )
                )
        return True

    def sync_db(self):
        """
        将这个结果表同步到实际数据库上
        1. 创建database
        2. 创建保留策略
        :return: True
        """
        # if self.is_database_exists():
        self.create_database()
        # self.create_rp()
        logger.debug("table_id->[%s] now is sync to db success" % self.table_id)

        return True

    def is_database_exists(self):
        """
        判断一个influx DB中的database是否存在
        :return: True | False
        """
        client = influxdb.client.InfluxDBClient(host=self.storage_cluster.domain_name, port=self.storage_cluster.port)

        return self.database in client.get_list_database()

    def add_field(self, field):
        """增加一个新的字段"""
        # InfluxDB不需要真的增加字段
        pass

    def get_client(self):
        pass

    @classmethod
    def clean_consul_config(cls):
        """
        清理掉不存在的consul key
        """
        # 遍历consul,删除已经不存在的key
        hash_consul = consul_tools.HashConsul()
        result_data = hash_consul.list(cls.CONSUL_CONFIG_CLUSTER_PATH)
        if not result_data[1]:
            return
        for item in result_data[1]:
            key = item["Key"]
            # 取路径最后一段，为主机名
            measurement = key.split("/")[-1]
            db = key.split("/")[-2]

            # 数据库里找不到的，就删掉
            length = len(cls.objects.filter(real_table_name=measurement, database=db))
            if length == 0:
                hash_consul.delete(key)
                logger.info("route info:{} deleted in consul".format(key))
            else:
                logger.info("route:{} has {} result,not delete".format(key, length))

    @classmethod
    def clean_redis_cluster_config(cls):
        """清理不存在的数据"""
        exist_table_id_list = cls.objects.values_list("table_id", flat=True)
        super().clean_redis_config(constants.INFLUXDB_PROXY_STORAGE_ROUTER_KEY, exist_table_id_list)

        logger.info("delete influxdb proxy successfully")

    def refresh_consul_cluster_config(self, is_version_refresh: bool = False, is_publish: bool = True):
        """
        刷新consul上的集群信息
        :return: None
        """

        hash_consul = consul_tools.HashConsul()
        hash_consul.put(key=self.consul_cluster_path, value=self.consul_cluster_config)
        logger.info("result_table->[%s] refresh cluster_info to consul success." % self.table_id)

        # TODO: 待推送 redis 数据稳定后，删除推送 consul 功能
        self.push_redis_data(is_publish)

        # 判断是否需要强行刷新一次consul版本
        if is_version_refresh:
            consul_tools.refresh_router_version()

    def get_metric_map(self):
        """
        获取metric及tag信息
        :return: [{
            "metric_name": "xxx",
            "metric_display_name": "XXX",
            "unit": "",
            "type": "float",
            "dimensions": [{
                "dimension_name": "",
                "dimension_display_name": ""
            }]
        }]
        """

        proxy = influxdb_tools.InfluxDBSchemaProxy(
            host=self.storage_cluster.domain_name,
            port=self.storage_cluster.port,
            database=self.database,
            measurement=self.real_table_name,
        )

        return proxy.get_metric_tag_values()

    def get_tag_values(self, tag_name):
        proxy = influxdb_tools.InfluxDBSchemaProxy(
            host=self.storage_cluster.domain_name,
            port=self.storage_cluster.port,
            database=self.database,
            measurement=self.real_table_name,
        )
        return proxy.get_tag_values(tag_name)

    @classmethod
    def refresh_additional_info_for_unify_query(cls):
        """刷新额外的信息，方便 unify query 查询使用

        现阶段包含数据源 ID, 所属的业务 ID, measurement 类型

        TODO: 待移除
        """
        from metadata.models import InfluxDBProxyStorage

        # 获取映射关系
        influxdb_proxy_ids = {
            obj["id"]: obj["proxy_cluster_id"] for obj in InfluxDBProxyStorage.objects.values("id", "proxy_cluster_id")
        }

        # 获取存在的路由表
        table_id_vm_rt_map = {
            obj["table_id"]: obj["influxdb_proxy_storage_id"]
            for obj in cls.objects.values("table_id", "influxdb_proxy_storage_id")
        }
        table_ids = list(table_id_vm_rt_map.keys())
        # 获取结果表的信息
        table_id_map = cls._get_table_info_by_table_ids(table_ids)
        # 获取数据源信息
        table_id_data_source_map = cls._get_data_source_by_table_ids(table_ids)
        # 获取结果表对应的业务 ID
        table_id_biz_id_map = cls._get_biz_id_by_table_ids(table_id_map, table_id_data_source_map)
        # 获取结果表类型
        table_id_measurement_type_map = cls._get_measurement_type(table_id_map)
        # 获取结果表对应的接入 vm 信息
        table_id_vm_info = cls._get_table_id_access_vm_data(table_ids)
        # 获取 vm 集群 ID
        vm_cluster_id_name = cls._get_vm_cluster_id_name()

        # 标识查询不到结果表的场景
        not_found_table_id = "not_found_table_id"
        # 组装数据，然后推送到 redis
        for table_id, influxdb_proxy_storage_id in table_id_vm_rt_map.items():
            data_id = (table_id_data_source_map.get(table_id) or {}).get("data_id") or not_found_table_id
            vm_info = table_id_vm_info.get(table_id) or {}
            cluster_id = influxdb_proxy_ids.get(influxdb_proxy_storage_id)

            val = {
                "bk_biz_id": table_id_biz_id_map.get(table_id) or not_found_table_id,
                "data_id": data_id,
                "measurement_type": table_id_measurement_type_map.get(table_id) or not_found_table_id,
                "vm_table_id": vm_info.get("vm_table_id") or "",
                "bcs_cluster_id": vm_info.get("bcs_cluster_id") or "",
                "is_influxdb_disabled": cluster_id in vm_cluster_id_name,
                "vm_storage_name": vm_cluster_id_name.get(cluster_id, ""),
            }
            cls.push_to_redis(
                constants.INFLUXDB_ADDITIONAL_INFO_FOR_UNIFY_QUERY, table_id, json.dumps(val), is_publish=False
            )
        # publish
        RedisTools.publish(constants.INFLUXDB_KEY_PREFIX, [constants.INFLUXDB_ADDITIONAL_INFO_FOR_UNIFY_QUERY])

    @classmethod
    def _get_table_id_access_vm_data(cls, table_ids: List[str]) -> Dict:
        """获取结果表和集群 ID 的关系"""
        from metadata.models import AccessVMRecord

        return {
            record["result_table_id"]: {
                "bcs_cluster_id": record["bcs_cluster_id"],
                "vm_table_id": record["vm_result_table_id"],
            }
            for record in AccessVMRecord.objects.filter(result_table_id__in=table_ids).values(
                "result_table_id", "bcs_cluster_id", "vm_result_table_id"
            )
        }

    @classmethod
    def _get_vm_cluster_id_name(cls) -> Dict:
        """获取 vm 集群 ID"""
        return {
            obj["cluster_id"]: obj["cluster_name"]
            for obj in ClusterInfo.objects.filter(cluster_type="victoria_metrics").values("cluster_id", "cluster_name")
        }

    @classmethod
    def _get_table_info_by_table_ids(cls, table_ids: List[str]) -> Dict[str, Dict]:
        """获取结果表信息"""
        rt_qs = ResultTable.objects.filter(table_id__in=table_ids).values("table_id", "schema_type", "bk_biz_id")
        return {
            obj["table_id"]: {
                "table_id": obj["table_id"],
                "schema_type": obj["schema_type"],
                "bk_biz_id": obj["bk_biz_id"],
            }
            for obj in rt_qs
        }

    @classmethod
    def _get_data_source_by_table_ids(cls, table_ids: List[str]) -> Dict[str, Dict]:
        """获取结果表对应的数据源信息"""
        from metadata.models import DataSource, DataSourceResultTable

        ds_rt_qs = DataSourceResultTable.objects.filter(table_id__in=table_ids).values("table_id", "bk_data_id")
        rt_ds_map = {obj["table_id"]: obj["bk_data_id"] for obj in ds_rt_qs}
        # 获取数据源名称和 ID
        data_id_name_map = {}
        data_id_space_uid_map = {}
        for ds in DataSource.objects.filter(bk_data_id__in=rt_ds_map.values()).values(
            "bk_data_id", "data_name", "space_uid"
        ):
            data_id_name_map[ds["bk_data_id"]] = ds["data_name"]
            data_id_space_uid_map[ds["bk_data_id"]] = ds["space_uid"]
        # 返回数据，格式: {table_id: {"data_id": "", "data_name": ""}}
        return {
            table_id: {
                "data_id": str(data_id),
                "data_name": data_id_name_map.get(data_id),
                "space_uid": data_id_space_uid_map.get(data_id),
            }
            for table_id, data_id in rt_ds_map.items()
        }

    @classmethod
    def _get_biz_id_by_table_ids(cls, table_id_map: Dict, table_id_data_source_map: Dict):
        """获取结果表所属的业务"""
        filter_params = {
            "bk_data_id__in": [table_id_data_source_map[table_id]["data_id"] for table_id in table_id_data_source_map]
        }

        from metadata.models import EventGroup, TimeSeriesGroup
        from metadata.models.space.space_data_source import get_real_biz_id

        # 过滤数据源是否存在
        data_id_ts_group_flag = {
            str(obj["bk_data_id"]): True for obj in TimeSeriesGroup.objects.filter(**filter_params).values("bk_data_id")
        }
        data_id_event_group_flag = {
            str(obj["bk_data_id"]): True for obj in EventGroup.objects.filter(**filter_params).values("bk_data_id")
        }
        # 获取结果表所属的业务 ID
        # TODO: 看需求可以增加到空间
        table_id_biz_id_map = {}
        for table_id, table_info in table_id_map.items():
            # NOTE: 应该不会有小于 0 的业务，当业务 ID 大于 0 时，直接返回
            bk_biz_id = table_info.get("bk_biz_id")
            if bk_biz_id > 0:
                table_id_biz_id_map[table_id] = str(bk_biz_id)
                continue

            # 获取 0 业务对应的真实业务 ID
            data_source = table_id_data_source_map.get(table_id) or {}
            data_name = data_source.get("data_name")
            space_uid = data_source.get("space_uid")
            data_id = str(data_source.get("data_id"))
            is_in_ts_group = data_id_ts_group_flag.get(data_id) or False
            is_in_event_group = data_id_event_group_flag.get(data_id) or False
            bk_biz_id = get_real_biz_id(data_name, is_in_ts_group, is_in_event_group, space_uid)
            table_id_biz_id_map[table_id] = str(bk_biz_id)

        return table_id_biz_id_map

    @classmethod
    def _get_measurement_type(cls, table_id_map: Dict) -> Dict:
        """获取 measurement 类型"""
        from metadata.models.space.space_redis import get_measurement_type_by_table_id

        # 组装需要的结果表列表
        table_list, table_id_list = [], []
        for table_id, table_info in table_id_map.items():
            table_id_list.append(table_id)
            table_list.append({"table_id": table_id, "schema_type": table_info["schema_type"]})

        return get_measurement_type_by_table_id(table_id_list, table_list)


class RedisStorage(models.Model, StorageResultTable):
    """Redis存储方案记录"""

    STORAGE_TYPE = ClusterInfo.TYPE_REDIS
    UPGRADE_FIELD_CONFIG = ("is_sentinel", "master_name")

    # 对应ResultTable的table_id
    table_id = models.CharField("结果表名", max_length=128, primary_key=True)
    # 默认命令是PUBLISH
    command = models.CharField("写入消息的命令", max_length=32, default="PUBLISH")
    key = models.CharField("存储键值", max_length=256)
    # 默认publish未用到该配置，为后续扩展预留
    db = models.IntegerField("redis DB配置", default=0)
    # 对应StorageCluster记录ID
    # 该字段配置，供监控存储外部使用
    storage_cluster_id = models.IntegerField("存储集群")
    # redis配置是否哨兵模式
    is_sentinel = models.BooleanField("是否哨兵模式", default=False)
    # redis哨兵模式下的master名字
    master_name = models.CharField("哨兵模式master名字", default="", max_length=128)

    @classmethod
    def create_table(
        cls,
        table_id,
        storage_cluster_id=None,
        key=None,
        db=0,
        command="PUBLISH",
        is_sentinel=False,
        master_name="",
        **kwargs,
    ):
        """
        实际创建结果表
        :param table_id: 结果表ID
        :param storage_cluster_id: 存储集群配置ID
        :param key: 写入到redis的键值配置
        :param db: redis DB，但该配置在publish命令下无效
        :param command: 写入redis的命令
        :param is_sentinel: 是否使用哨兵模式
        :param master_name: 哨兵master名字
        :param kwargs: 其余的额外配置，目前无效
        :return: storage object
        """

        # 0. 判断是否需要使用默认集群信息
        if storage_cluster_id is None:
            storage_cluster_id = ClusterInfo.objects.get(
                cluster_type=ClusterInfo.TYPE_REDIS, is_default_cluster=True
            ).cluster_id

        # 如果有提供集群信息，需要判断
        else:
            if not ClusterInfo.objects.filter(
                cluster_type=ClusterInfo.TYPE_REDIS, cluster_id=storage_cluster_id
            ).exists():
                logger.error(
                    "cluster_id->[%s] is not exists or is not redis cluster, something go wrong?" % storage_cluster_id
                )
                raise ValueError(_("存储集群配置有误，请确认或联系管理员处理"))

        # 1. 校验table_id， key是否存在冲突
        if cls.objects.filter(table_id=table_id).exists():
            logger.error("result_table->[%s] already has redis storage config, nothing will add." % table_id)
            raise ValueError(_("结果表[%s]配置已存在，请确认后重试") % table_id)

        # 如果未有执行key，则改为table_id
        key = key if key is not None else table_id
        # key的构造为 ${prefix}_${key}
        key = "_".join([config.REDIS_KEY_PREFIX, key])
        # 由于redis不必提前创建key，创建记录完成后即可
        new_record = cls.objects.create(
            table_id=table_id,
            storage_cluster_id=storage_cluster_id,
            command=command,
            key=key,
            db=db,
            is_sentinel=is_sentinel,
            master_name=master_name,
        )

        logger.info("table->[%s] now has create redis storage config" % table_id)
        return new_record

    @property
    def consul_config(self):
        """返回一个实际存储的consul配置"""

        consul_config = {
            "storage_config": {
                "db": self.db,
                "key": self.key,
                "command": self.command,
                "is_sentinel": self.is_sentinel,
                "master_name": self.master_name,
            }
        }
        # 添加集群信息
        consul_config.update(self.storage_cluster.consul_config)

        # 将存储的修改时间去掉，防止MD5命中失败
        consul_config["cluster_config"].pop("last_modify_time")

        return consul_config

    def get_client(self):
        """获取该结果表的客户端句柄"""
        pass

    def add_field(self, field):
        """增加一个新的字段"""
        # redis算是无结构表数据库，不必提供方法
        pass


class KafkaStorage(models.Model, StorageResultTable):
    """Kafka存储方案记录"""

    STORAGE_TYPE = ClusterInfo.TYPE_KAFKA
    UPGRADE_FIELD_CONFIG = ("partition", "retention")

    # 对应ResultTable的table_id
    table_id = models.CharField("结果表名", max_length=128, primary_key=True)
    topic = models.CharField("topic", max_length=256)
    partition = models.IntegerField("topic分区数量", default=1)
    # 对应StorageCluster记录ID
    # 该字段配置，供监控存储外部使用
    storage_cluster_id = models.IntegerField("存储集群")
    # 数据过期时间配置为半小时，原因是kafka数据通常是为实时告警使用，该类告警不必保留过长时间
    retention = models.IntegerField("保存数据超时时间", default=1800000)

    def __unicode__(self):
        return "{}->[t:{} p:{}]".format(self.table_id, self.topic, self.partition)

    class Meta:
        verbose_name = "Kafka存储配置"
        verbose_name_plural = "Kafka存储配置"

    @classmethod
    def create_table(
        cls,
        table_id,
        is_sync_db=False,
        storage_cluster_id=None,
        topic=None,
        partition=1,
        retention=1800000,
        use_default_format=True,
        **kwargs,
    ):
        """
        实际创建结果表
        :param table_id: 结果表ID
        :param is_sync_db: 是否需要同步到存储
        :param storage_cluster_id: 存储集群配置ID
        :param topic: topic
        :param partition: topic分区
        :param retention: 数据过期时间
        :param use_default_format: 使用默认的 topic 规则
        :param kwargs: 其余的额外配置，目前无效
        :return: storage object
        """

        # 0. 判断是否需要使用默认集群信息
        if storage_cluster_id is None:
            if settings.DEFAULT_KAFKA_STORAGE_CLUSTER_ID is not None:
                storage_cluster_id = settings.DEFAULT_KAFKA_STORAGE_CLUSTER_ID
            else:
                storage_cluster_id = ClusterInfo.objects.get(
                    cluster_type=ClusterInfo.TYPE_KAFKA, is_default_cluster=True
                ).cluster_id

        # 如果有提供集群信息，需要判断
        else:
            if not ClusterInfo.objects.filter(
                cluster_type=ClusterInfo.TYPE_KAFKA, cluster_id=storage_cluster_id
            ).exists():
                logger.error(
                    "cluster_id->[%s] is not exists or is not redis cluster, something go wrong?" % storage_cluster_id
                )
                raise ValueError(_("存储集群配置有误，请确认或联系管理员处理"))

        # 1. 校验table_id， key是否存在冲突
        if cls.objects.filter(table_id=table_id).exists():
            logger.error("result_table->[%s] already has redis storage config, nothing will add." % table_id)
            raise ValueError(_("结果表[%s]配置已存在，请确认后重试") % table_id)

        # 如果未有指定key，则改为table_id
        topic = topic if topic is not None else table_id
        # topic的构造为 ${prefix}_${key}
        if use_default_format:
            topic = "_".join([config.KAFKA_TOPIC_PREFIX_STORAGE, topic])

        new_record = cls.objects.create(
            table_id=table_id,
            storage_cluster_id=storage_cluster_id,
            topic=topic,
            partition=partition,
            retention=retention,
        )

        # 需要确保topic存在
        if is_sync_db:
            new_record.ensure_topic()

        logger.info("table->[%s] now has create kafka storage config" % table_id)
        return new_record

    @property
    def consul_config(self):
        """返回一个实际存储的consul配置"""

        consul_config = {"storage_config": {"topic": self.topic, "partition": self.partition}}
        # 添加集群信息
        consul_config.update(self.storage_cluster.consul_config)

        # 将存储的修改时间去掉，防止MD5命中失败
        consul_config["cluster_config"].pop("last_modify_time")

        return consul_config

    def get_client(self):
        """获取该结果表的客户端句柄"""
        pass

    def add_field(self, field):
        """增加一个新的字段"""
        # kafka算是无结构表数据库，不必提供方法
        pass

    def ensure_topic(self):
        """
        确保这个存储的topic存在
        :return: True | raise Exception
        """
        logger.info("topic->[%s] will auto create by kafka server, nothing will do any more.", self.topic)
        return True


class ESStorage(models.Model, StorageResultTable):
    """ES存储配置信息"""

    CONSUL_PREFIX_PATH = "%s/unify-query/data/es/info" % config.CONSUL_PATH
    CONSUL_VERSION_PATH = "%s/unify-query/version/es/info" % config.CONSUL_PATH
    CONSUL_ALIAS_FORMAT = "{index}_{time}_read"
    CONSUL_DATE_FORMAT = "20060102"

    STORAGE_TYPE = ClusterInfo.TYPE_ES
    UPGRADE_FIELD_CONFIG = (
        "retention",
        "slice_size",
        "slice_gap",
        "index_settings",
        "mapping_settings",
        "storage_cluster_id",
        "warm_phase_days",
        "warm_phase_settings",
    )
    JSON_FIELDS = ("warm_phase_settings",)
    # 从ES7开始移除_type
    ES_REMOVE_TYPE_VERSION = 7
    TIME_ZONE_MAX = 12
    TIME_ZONE_MIN = -12

    # 对应ResultTable的table_id
    table_id = models.CharField("结果表名", max_length=128, primary_key=True)
    # 格式化配置字符串，用于追加到table_id后，作为index的创建方案，默认格式类似为20190910194802
    date_format = models.CharField("日期格式化配置", max_length=64, default="%Y%m%d%H")

    # index切分大小阈值，单位GB，默认是500GB
    slice_size = models.IntegerField("index大小切分阈值", default=500)
    # index分片时间间隔，单位分钟，默认2小时
    slice_gap = models.IntegerField("index分片时间间隔", default=120)
    # 存储时间, 单位天，默认30天
    retention = models.IntegerField("index保存时间", default=30)

    # 索引数据分配配置
    # 通过配置，将一定天数前的索引数据分配到拥有特定属性的节点
    warm_phase_days = models.IntegerField("切换到暖数据的等待天数", default=0)
    # 暖数据配置：dict
    # 参考：https://www.elastic.co/guide/en/elasticsearch/reference/current/shard-allocation-filtering.html
    # {
    #   "allocation_attr_name": "box_type",  // 切换路由的节点属性名称
    #   "allocation_attr_value": "warm",     // 切换路由的节点属性值
    #   "allocation_type": "include",   // 属性匹配类型，可选 require, include, exclude 等
    # }
    warm_phase_settings = JsonField("暖数据配置", default={})
    # 时区设置 取值[12]-[-12], 默认0时区
    time_zone = models.IntegerField("时区设置", default=0)

    # 下方三个配置，对于metadata都是透明存储的方式，供用户直接配置使用
    # 从而降低对版本等信息的依赖，格式应该是JSON格式，以便可以直接在创建请求的body中使用
    index_settings = models.TextField("索引配置信息")
    mapping_settings = models.TextField("别名配置信息")
    storage_cluster_id = models.IntegerField("存储集群")

    @classmethod
    def refresh_consul_table_config(cls):
        """
        刷新查询模块的table consul配置
        :return: None
        """

        hash_consul = consul_tools.HashConsul()

        # 1. 获取需要刷新的信息列表
        info_list = cls.objects.all()

        total_count = info_list.count()
        logger.debug("total find->[{}] es table info to refresh".format(total_count))

        # 2. 构建需要刷新的字典信息
        refresh_dict = {}
        for table_info in info_list:
            # 如果结果表已经废弃了，则不需要继续更新路径
            if table_info.is_index_enable():
                refresh_dict[table_info.table_id] = table_info
                continue

            logger.info(
                "table_id->[%s] is disable now, won`t refresh consul data any more and will clean it.",
                table_info.table_id,
            )
            consul_path = "/".join([cls.CONSUL_PREFIX_PATH, table_info.table_id])

            # 同时考虑清理consul上的路径
            if hash_consul.get(consul_path) is not None:
                logger.info(
                    "table_id->[%s] is disable now but consul path exists, will delete the consul path.",
                    table_info.table_id,
                )
                hash_consul.delete(consul_path)

        # 3. 遍历所有的字典信息并写入至consul
        for table_id, table_info in list(refresh_dict.items()):
            consul_path = "/".join([cls.CONSUL_PREFIX_PATH, table_id])

            hash_consul.put(
                key=consul_path,
                value={
                    "storage_id": table_info.storage_cluster_id,
                    "alias_format": cls.CONSUL_ALIAS_FORMAT,
                    "date_format": cls.CONSUL_DATE_FORMAT,
                    "date_step": table_info.slice_gap,
                },
            )
            logger.debug("consul path->[{}] is refresh with value->[{}] success.".format(consul_path, refresh_dict))

        hash_consul.put(key=cls.CONSUL_VERSION_PATH, value={"time": time.time()})
        logger.info("all es table info is refresh to consul success count->[%s]." % total_count)

    def create_es_index(self, is_sync_db: bool):
        """创建 es 索引"""
        table_id = self.table_id
        if is_sync_db:
            # 只往前创建一个index
            self.create_index_and_aliases(self.slice_gap)
            logger.info("result_table->[{}] has create es storage index".format(table_id))
        else:
            from metadata.task import tasks

            tasks.create_es_storage_index.delay(table_id=table_id)
            logger.info("result_table->[{}] create async with celery task".format(table_id))

    @classmethod
    def create_table(
        cls,
        table_id,
        is_sync_db=True,
        date_format="%Y%m%d%H",
        slice_size=500,
        slice_gap=120,
        index_settings=None,
        mapping_settings=None,
        cluster_id=None,
        retention=30,
        warm_phase_days=0,
        warm_phase_settings=None,
        time_zone=0,
        enable_create_index=True,
        **kwargs,
    ):
        """
        实际创建结果表
        :param table_id: 结果表ID
        :param is_sync_db: 是否需要同步创建结果表
        :param date_format: 时间格式，用于拼接index及别名
        :param slice_size: 切分大小，不提供使用默认值
        :param slice_gap: 切分时间间隔，不提供使用默认值
        :param index_settings: index创建配置，如果不提供，默认为{}(无配置)
        :param mapping_settings: index创建时的mapping配置，如果不提供，默认为{}，但是字段信息将会被覆盖
        :param cluster_id: 集群ID，如果不提供使用默认的ES集群
        :param retention: 保留时间
        :param warm_phase_days: 暖数据执行分配的等待天数，默认为 0 (不开启)
        :param warm_phase_settings: 暖数据切换配置，当 warm_phase_days > 0 时，此项必填
        :param time_zone: 时区设置，默认零时区
        :param enable_create_index: 启用创建索引，默认为 True
        :param kwargs: 其他配置参数
        :return:
        """
        # 0. 判断是否需要使用默认集群信息
        if cluster_id is None:
            cluster_id = ClusterInfo.objects.get(cluster_type=ClusterInfo.TYPE_ES, is_default_cluster=True).cluster_id

        # 如果有提供集群信息，需要判断
        else:
            if not ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_ES, cluster_id=cluster_id).exists():
                logger.error("cluster_id->[%s] is not exists or is not redis cluster, something go wrong?" % cluster_id)
                raise ValueError(_("存储集群配置有误，请确认或联系管理员处理"))

        # 1. 校验table_id， key是否存在冲突
        if cls.objects.filter(table_id=table_id).exists():
            logger.error("result_table->[%s] already has redis storage config, nothing will add." % table_id)
            raise ValueError(_("结果表[%s]配置已存在，请确认后重试") % table_id)

        # 测试date_format是否正确可用的 -- 格式化结果的数据只能包含数字，不能有其他结果
        test_str = datetime.datetime.utcnow().strftime(date_format)
        if re.match(r"^\d+$", test_str) is None:
            logger.error("result_table->[{}] date_format contains none digit info, it is bad.".format(table_id))
            raise ValueError(_("时间格式不允许包含非数字格式"))

        # 校验分配配置
        if warm_phase_days > 0:
            if not warm_phase_settings:
                logger.error("result_table->[{}] warm_phase_settings is empty, but min_days > 0.".format(table_id))
                raise ValueError(_("warm_phase_settings 不能为空"))
            for required_field in ["allocation_attr_name", "allocation_attr_value", "allocation_type"]:
                if not warm_phase_settings.get(required_field):
                    raise ValueError(_("warm_phase_settings.{} 不能为空").format(required_field))

        # validate time_zone at 12 -> -12
        if not (cls.TIME_ZONE_MAX >= time_zone >= cls.TIME_ZONE_MIN):
            raise ValueError(_("time_zone -> [{}] 设置不合法").format(time_zone))

        warm_phase_settings = {} if warm_phase_settings is None else warm_phase_settings

        # 判断两个TextField的配置内容
        index_settings = {} if index_settings is None else index_settings
        mapping_settings = {} if mapping_settings is None else mapping_settings

        # alias settings目前暂时没有用上，在参数和配置中都没有更新
        new_record = cls.objects.create(
            table_id=table_id,
            date_format=date_format,
            slice_size=slice_size,
            slice_gap=slice_gap,
            retention=retention,
            warm_phase_days=warm_phase_days,
            warm_phase_settings=warm_phase_settings,
            index_settings=json.dumps(index_settings),
            mapping_settings=json.dumps(mapping_settings),
            storage_cluster_id=cluster_id,
            time_zone=time_zone,
        )
        logger.info("result_table->[{}] now has es_storage will try to create index.".format(table_id))

        # 判断是否启用创建索引，默认是启用
        if enable_create_index:
            new_record.create_es_index(is_sync_db)

        return new_record

    @property
    def index_body(self):
        """
        ES创建索引的配置内容
        :return: dict, 可以直接
        """
        body = {"settings": json.loads(self.index_settings), "mappings": json.loads(self.mapping_settings)}

        # 构建mapping内容
        # 将所有properties先去掉，防止用户注入了自行的字段内容
        properties = body["mappings"]["properties"] = {}
        for field in ResultTableField.objects.filter(table_id=self.table_id):
            # 直接注入这个字段的配置
            properties[field.field_name] = ResultTableFieldOption.get_field_option_es_format(
                table_id=self.table_id, field_name=field.field_name
            )

        # 按ES版本返回构建body内容
        if self.es_version < self.ES_REMOVE_TYPE_VERSION:
            body["mappings"] = {self.table_id: body["mappings"]}
        return body

    @property
    def index_re_v1(self):
        """获取这个存储的正则匹配内容"""
        pattern = r"{}_(?P<datetime>\d+)_(?P<index>\d+)".format(self.index_name)
        return re.compile(pattern)

    @property
    def index_re_v2(self):
        """获取这个存储的正则匹配内容"""
        pattern = r"^v2_{}_(?P<datetime>\d+)_(?P<index>\d+)$".format(self.index_name)
        return re.compile(pattern)

    @property
    def index_re_common(self):
        """获取这个存储的正则匹配内容"""
        pattern = r"^(v2_)?{}_(?P<datetime>\d+)_(?P<index>\d+)$".format(self.index_name)
        return re.compile(pattern)

    @property
    def write_alias_re(self):
        """获取写入别名的正则匹配"""
        pattern = r"write_(?P<datetime>\d+)_{}".format(self.index_name)
        return re.compile(pattern)

    @property
    def old_write_alias_re(self):
        """获取旧版写入别名的正则匹配"""
        pattern = r"{}_(?P<datetime>\d+)_write".format(self.index_name)
        return re.compile(pattern)

    @property
    def read_alias_re(self):
        """获取读取别名的正则匹配"""
        pattern = r"{}_(?P<datetime>\d+)_read".format(self.index_name)
        return re.compile(pattern)

    @property
    def index_name(self):
        """返回该index的名字"""
        return self.table_id.replace(".", "_")

    @property
    def es_version(self):
        """
        获取ES版本号
        """
        cluster_info = ClusterInfo.objects.get(cluster_id=self.storage_cluster_id)
        try:
            cluster_version = int(cluster_info.version.split(".")[0])
        except Exception:
            logger.error(
                "cluster_id->[{}] get version error->[{}] ".format(self.storage_cluster_id, traceback.format_exc())
            )
            cluster_version = config.ES_CLUSTER_VERSION_DEFAULT
        return cluster_version

    @property
    def consul_config(self):
        """返回一个实际存储的consul配置"""
        standard_time = datetime.datetime.strptime("200601021504", "%Y%m%d%H%M%S")

        consul_config = {
            "storage_config": {
                "index_datetime_format": "write_{}".format(standard_time.strftime(self.date_format)),
                "index_datetime_timezone": self.time_zone,
                "date_format": self.date_format,
                "slice_size": self.slice_size,
                "slice_gap": self.slice_gap,
                "retention": self.retention,
                "warm_phase_days": self.warm_phase_days,
                "warm_phase_settings": self.warm_phase_settings,
                "base_index": self.table_id.replace(".", "_"),
                "index_settings": json.loads(self.index_settings),
                "mapping_settings": json.loads(self.mapping_settings),
            }
        }
        # 添加集群信息
        consul_config.update(self.storage_cluster.consul_config)

        # 将存储的修改时间去掉，防止MD5命中失败
        consul_config["cluster_config"].pop("last_modify_time")

        return consul_config

    @property
    def now(self):
        return arrow.utcnow().replace(hours=self.time_zone).datetime

    def is_red(self):
        """判断 es 集群是否 red"""
        try:
            es_session = es_tools.es_retry_session(es_client=self.es_client, retry_num=3, backoff_factor=0.1)
            healthz = es_session.cluster.health()
            if healthz["status"] == "red":
                return True
            return False
        except Exception as e:
            logger.error("query es cluster error by retry 3, error: %s", e)
            return True

    def is_index_enable(self):
        """判断index是否启用中"""

        # 判断如果结果表已经废弃了，那么不再进行index的创建
        if not ResultTable.objects.filter(table_id=self.table_id, is_enable=True, is_deleted=False).exists():
            logger.info("table_id->[%s] now is delete or disable, no index will create.", self.table_id)
            return False

        # 同时需要增加判断这个结果表是否可能遗留的自定义事件上报，需要考虑自定义上报已经关闭了
        try:
            # 查找发现，1. 这个es存储是归属于自定义事件的，而且 2. 不是在启动且未被删除的，那么不需要创建这个索引
            event_group = EventGroup.objects.get(table_id=self.table_id)

            if not event_group.is_enable or event_group.is_delete:
                logger.info(
                    "table_id->[%s] is belong to event group and is disable or deleted, no index will create",
                    self.table_id,
                )
                return False

        except EventGroup.DoesNotExist:
            # 如果查找失败，那么这个存储是日志平台，而且rt没有被删除或废弃，需要继续建立index
            logger.info("table_id->[%s] belong to log search, will create it.", self.table_id)

        return True

    def search_format_v2(self):
        return f"v2_{self.index_name}_*"

    def search_format_v1(self):
        return f"{self.index_name}_*"

    def index_exist(self):
        """
        判断该index是否已经存在,优先v2，随后v1
        :return: True | False
        """
        es_client = self.get_client()
        stat_info_list = es_client.indices.stats(self.search_format_v2())
        for stat_index_name in list(stat_info_list["indices"].keys()):
            re_result = self.index_re_v2.match(stat_index_name)
            if re_result:
                logger.debug("table_id->[%s] found v2 index list->[%s]", self.table_id, str(stat_info_list))
                return True
        stat_info_list = es_client.indices.stats(self.search_format_v1())
        for stat_index_name in list(stat_info_list["indices"].keys()):
            re_result = self.index_re_v1.match(stat_index_name)
            if re_result:
                logger.info("table_id->[%s] found v1 index list->[%s]", self.table_id, str(stat_info_list))
                return True
        logger.info("table_id->[%s] no index", self.table_id)
        return False

    def current_index_info(self):
        """
        返回当前使用的最新index相关的信息
        :return: {
            "datetime_object": max_datetime_object,
            "index": 0,
            "size": 123123,  # index大小，单位byte
        }
        """
        es_client = self.get_client()
        # stats格式为：{
        #   "indices": {
        #       "${index_name}": {
        #           "total": {
        #               "store": {
        #                   "size_in_bytes": 1000
        #               }
        #           }
        #       }
        #   }
        # }
        index_re = None
        index_version = ""
        # 查找index,找不到v2的就找v1的
        stat_info_list = es_client.indices.stats(self.search_format_v2())
        if len(stat_info_list["indices"]) != 0:
            index_version = "v2"
            index_re = self.index_re_v2
        else:
            stat_info_list = es_client.indices.stats(self.search_format_v1())
            if len(stat_info_list["indices"]) != 0:
                index_version = "v1"
                index_re = self.index_re_v1

        # 如果index_re为空，说明没找到任何可用的index
        if index_version == "":
            logger.info("index->[%s] has no index now, will raise a fake not found error", self.index_name)
            raise elasticsearch5.NotFoundError(self.index_name)

        # 1.1 判断获取最新的index
        max_index = 0
        max_datetime_object = None
        for stat_index_name in list(stat_info_list["indices"].keys()):
            re_result = index_re.match(stat_index_name)
            if re_result is None:
                # 去掉一个整体index的计数
                logger.warning("index->[%s] is not match re, maybe something go wrong?", stat_index_name)
                continue

            # 获取实际的count及时间对象
            current_index = int(re_result.group("index"))
            current_datetime_str = re_result.group("datetime")
            current_datetime_object = datetime_str_to_datetime(current_datetime_str, self.date_format, self.time_zone)
            logger.info(
                "going to detect index->[%s] datetime->[%s] count->[%s]",
                stat_index_name,
                current_index,
                current_datetime_str,
            )

            # 初始化轮，直接赋值
            if max_datetime_object is None:
                max_index = current_index
                max_datetime_object = current_datetime_object
                logger.debug(
                    "current round is init round, will use datetime->[%s] and count->[%s]",
                    current_datetime_str,
                    current_index,
                )
                continue

            # 判断获取最新的index内容
            # 当时间较大的时候，直接赋值使用
            if current_datetime_object > max_datetime_object:
                max_datetime_object = current_datetime_object
                max_index = current_index
                logger.debug(
                    "current time->[%s] is newer than max time->[%s] will use it and reset count->[%s]",
                    current_datetime_str,
                    max_datetime_object.strftime(self.date_format),
                    current_index,
                )
                continue

            # 判断如果时间一致且index较大，需要更新替换
            if current_datetime_object == max_datetime_object and current_index > max_index:
                max_index = current_index
                logger.debug(
                    "current time->[%s] found newer index->[%s] will use it",
                    max_datetime_object.strftime(self.date_format),
                    current_index,
                )

        return {
            "index_version": index_version,
            "datetime_object": max_datetime_object,
            "index": max_index,
            "size": stat_info_list["indices"][f"{self.make_index_name(max_datetime_object, max_index, index_version)}"][
                "primaries"
            ]["store"]["size_in_bytes"],
        }

    def make_index_name(self, datetime_object, index, version):
        """根据传入的时间和index，创建返回一个index名"""
        if version == "v2":
            return f"v2_{self.index_name}_{datetime_object.strftime(self.date_format)}_{index}"
        return f"{self.index_name}_{datetime_object.strftime(self.date_format)}_{index}"

    def get_client(self):
        """获取该结果表的客户端句柄"""
        return es_tools.get_client(self.storage_cluster_id)

    es_client = cached_property(get_client, name="es_client")

    def add_field(self, field):
        """需要修改ES的mapping"""
        pass

    def create_index(self, ahead_time=1440):
        """
        创建index，具有提前创建index的能力
        :param ahead_time: 需要提前创建多少分钟后的index
        :return: True | raise Exception
        """

        # 判断如果结果表已经废弃了，那么不再进行index的创建
        if not ResultTable.objects.filter(table_id=self.table_id, is_enable=True, is_deleted=False).exists():
            logger.info("table_id->[%s] now is delete or disable, no index will create.", self.table_id)
            return

        # 同时需要增加判断这个结果表是否可能遗留的自定义事件上报，需要考虑自定义上报已经关闭了
        try:
            # 查找发现，1. 这个es存储是归属于自定义事件的，而且 2. 不是在启动且未被删除的，那么不需要创建这个索引
            event_group = EventGroup.objects.get(table_id=self.table_id)

            if not event_group.is_enable or event_group.is_delete:
                logger.info(
                    "table_id->[%s] is belong to event group and is disable or deleted, no index will create",
                    self.table_id,
                )
                return

        except EventGroup.DoesNotExist:
            # 如果查找失败，那么这个存储是日志平台，而且rt没有被删除或废弃，需要继续建立index
            logger.info("table_id->[%s] belong to log search, will create it.", self.table_id)

        now_time = self.now
        now_gap = 0

        # 1. 获取客户端
        es_client = self.get_client()
        # 统一的将所有【.】分割符改为【_】
        index_name = self.index_name

        # 3. 遍历创建所有的index
        # 创建的方式，是从近到远的创建
        while now_gap <= ahead_time:
            try:
                delete_index_list = []
                current_time = now_time + datetime.timedelta(minutes=now_gap)
                current_time_str = current_time.strftime(self.date_format)

                current_index_wildcard = "{}_{}_*".format(self.index_name, current_time_str)

                # 获取这个index的大小信息，这是需要兼容判断是否有未来数据写入到index上了
                stat_info = es_client.indices.stats(current_index_wildcard)
                max_index = -1

                # 判断获取最大的index名字
                for stat_index_name in list(stat_info["indices"].keys()):
                    re_result = self.index_re.match(stat_index_name)
                    if re_result is None:
                        # 去掉一个整体index的计数
                        logger.warning("index->[{}] is not match re, maybe something go wrong?".format(index_name))
                        continue

                    current_index_count = int(re_result.group("index"))
                    if max_index < current_index_count:
                        max_index = current_index_count

                # 获取现在当前最大的index
                # 注意，这时候的index有可能是-1的名字，例如：2_test_log_20191112_-1
                max_index_name = "{}_{}_{}".format(self.index_name, current_time_str, max_index)

                # 如果已经存在的index，不必重复创建
                is_index_exists = es_client.indices.exists(index=max_index_name)
                # 如果一个index是不存在的，则默认需要创建
                should_create = not is_index_exists

                # 判断index如果是存在的，需要判断：
                # 1. 是否大小需要进行切片分割
                # 2. 是否字段有变化，需要进行重建
                if is_index_exists:
                    # 判断字段是否一致，如果不一致，需要创建新的删除并创建新的
                    if not self.is_mapping_same(max_index_name):
                        logger.info(
                            "index->[{}] is exists, and field type is not the same as database, "
                            "will create a new index.".format(max_index_name)
                        )
                        should_create = True

                    # 判断大小是否有超限，需要切片
                    try:
                        size_in_bytes = stat_info["indices"][max_index_name]["total"]["store"]["size_in_bytes"]
                    except KeyError:
                        logger.warning(
                            "ops, index->[{}] is not exists in stat_info, maybe is not exists?".format(max_index_name)
                        )
                    else:
                        if size_in_bytes / 1024.0 / 1024.0 / 1024.0 > self.slice_size:
                            logger.info(
                                "index->[{}] size->[{}]bytes now is bigger than slice_size->[{}]GB, will "
                                "create new one".format(max_index_name, size_in_bytes, self.slice_size)
                            )
                            should_create = True

                # 判断是否需要重建了，不用重建的，直接下一个周期
                if not should_create:
                    logger.info("index->[{}] meet all config, nothing will create.".format(max_index_name))
                    # gap的更新在finally进行
                    continue

                # 如果判断要创建index，需要先判断这个index是否有数据了
                try:
                    # 如果是存在数据的，需要创建一个新的index
                    if es_client.count(index=max_index_name).get("count", 0) != 0:
                        logger.info(
                            "index->[{}] already has data, will keep it and create new index.".format(max_index_name)
                        )
                        # 有数据的，需要增加index
                        current_index = "{}_{}_{}".format(index_name, current_time_str, max_index + 1)
                        delete_index_list.append(max_index_name)

                    # 不存在数据的，则删除并重新创建
                    else:
                        es_client.indices.delete(max_index_name)
                        logger.warning(
                            "index->[{}] is differ from database config, "
                            "will be delete and recreated.".format(max_index_name)
                        )
                        # 创建的新index，使用已有的最大index名即可
                        # 此处可以保留已有的别名配置，不用删除
                        current_index = max_index_name

                except (elasticsearch5.NotFoundError, elasticsearch.NotFoundError, elasticsearch6.NotFoundError):
                    # 很可能是0号或者-1号的index没有创建，所以判断count不存在
                    logger.warning("index->[{}] may not exists, cannot found count? will create new one.")
                    # 看下是否-1的index，需要调整为0的
                    current_index = (
                        "{}_{}_0".format(index_name, current_time_str) if max_index == -1 else max_index_name
                    )

                # 创建索引需要增加一个请求超时的防御
                logger.info("index->[{}] trying to create, index_body->[{}]".format(index_name, self.index_body))
                es_client.indices.create(index=current_index, body=self.index_body, params={"request_timeout": 30})
                logger.info("index->[{}] now is created.".format(current_index))

                # 需要将对应的别名指向这个新建的index
                # 新旧类型的alias都会创建，防止transfer未更新导致异常
                new_current_alias_name = "write_{}_{}".format(current_time_str, index_name)
                old_current_alias_name = "{}_{}_write".format(index_name, current_time_str)

                es_client.indices.put_alias(index=current_index, name=new_current_alias_name)
                es_client.indices.put_alias(index=current_index, name=old_current_alias_name)

                logger.info(
                    "index->[{}] now has write alias->[{} | {}]".format(
                        current_index, new_current_alias_name, old_current_alias_name
                    )
                )

                # 清理别名
                if len(delete_index_list) != 0:
                    es_client.indices.delete_alias(index=",".join(delete_index_list), name=old_current_alias_name)
                    es_client.indices.delete_alias(index=",".join(delete_index_list), name=new_current_alias_name)
                    logger.info(
                        "index->[{}] has delete relation to alias->[{} | {}]".format(
                            delete_index_list, old_current_alias_name, new_current_alias_name
                        )
                    )

            finally:
                logger.info("all operations for index->[{}] gap->[{}] now is done.".format(self.table_id, now_gap))
                now_gap += self.slice_gap

        return True

    def create_or_update_aliases(self, ahead_time=1440):
        """
        更新alias，如果有已存在的alias，则将其指向最新的index，并根据ahead_time前向预留一定的alias
        """
        es_client = self.get_client()
        current_index_info = self.current_index_info()
        last_index_name = self.make_index_name(
            current_index_info["datetime_object"], current_index_info["index"], current_index_info["index_version"]
        )

        now_datetime_object = self.now

        now_gap = 0
        index_name = self.index_name

        while now_gap <= ahead_time:
            round_time = now_datetime_object + datetime.timedelta(minutes=now_gap)
            round_time_str = round_time.strftime(self.date_format)

            try:
                round_alias_name = f"write_{round_time_str}_{index_name}"
                round_read_alias_name = f"{index_name}_{round_time_str}_read"

                # 3.1 判断这个别名是否有指向旧的index，如果存在则需要解除
                try:
                    # 此处是非通配的别名，所以会有NotFound的异常
                    index_list = es_client.indices.get_alias(name=round_alias_name).keys()

                    # 排除已经指向最新index的alias
                    delete_list = []
                    for alias_index in index_list:
                        if alias_index != last_index_name:
                            delete_list.append(alias_index)

                    logger.info(
                        "table_id->[%s] found alias_name->[%s] is relay with index->[%s] all will be deleted.",
                        self.table_id,
                        round_alias_name,
                        delete_list,
                    )
                except (elasticsearch5.NotFoundError, elasticsearch.NotFoundError, elasticsearch6.NotFoundError):
                    # 可能是在创建未来的alias，所以不一定会有别名关联的index
                    logger.info(
                        "table_id->[%s] alias_name->[%s] found not index relay, will not delete any thing.",
                        self.table_id,
                        round_alias_name,
                    )
                    delete_list = []

                # 3.2 需要将循环中的别名都指向了最新的index
                es_client.indices.update_aliases(
                    body={
                        "actions": [
                            {"add": {"index": last_index_name, "alias": round_alias_name}},
                            {"add": {"index": last_index_name, "alias": round_read_alias_name}},
                        ]
                    }
                )

                logger.info(
                    "table_id->[%s] now has index->[%s] and alias->[%s | %s]",
                    self.table_id,
                    last_index_name,
                    round_alias_name,
                    round_read_alias_name,
                )

                # 只有当index相关列表不为空的时候，才会进行别名关联清理
                if len(delete_list) != 0:
                    index_list_str = ",".join(delete_list)
                    es_client.indices.delete_alias(index=index_list_str, name=round_alias_name)
                    logger.info(
                        "table_id->[%s] index->[%s] alias->[%s] relations now had delete.",
                        self.table_id,
                        delete_list,
                        round_alias_name,
                    )

            finally:
                logger.info("all operations for index->[{}] gap->[{}] now is done.".format(self.table_id, now_gap))
                # slice_gap maybe zero, will cause dead loop
                if self.slice_gap <= 0:
                    return
                now_gap += self.slice_gap

    def create_index_and_aliases(self, ahead_time=1440):
        self.create_index_v2()
        self.create_or_update_aliases(ahead_time)

    def update_index_and_aliases(self, ahead_time=1440):
        self.update_index_v2()
        self.create_or_update_aliases(ahead_time)

    def create_index_v2(self):
        """
        创建全新的index序列，以及指向它的全新alias
        """
        if not self.is_index_enable():
            return False

        now_datetime_object = self.now
        es_client = self.get_client()
        new_index_name = self.make_index_name(now_datetime_object, 0, "v2")
        # 创建index
        es_client.indices.create(index=new_index_name, body=self.index_body, params={"request_timeout": 30})
        logger.info("table_id->[%s] has created new index->[%s]", self.table_id, new_index_name)
        return True

    def update_index_v2(self):
        """
        判断index是否需要分裂，并提前建立index别名的功能
        此处仍然保留每个小时创建新的索引，主要是为了在发生异常的时候，可以降低影响的索引范围（最多一个小时）
        :return: True | raise Exception
        """
        if not self.is_index_enable():
            return False

        now_datetime_object = self.now

        # 0. 获取客户端
        es_client = self.get_client()

        # 1. 获取当前最新的index
        try:
            current_index_info = self.current_index_info()
            last_index_name = self.make_index_name(
                current_index_info["datetime_object"], current_index_info["index"], current_index_info["index_version"]
            )
            index_size_in_byte = current_index_info["size"]

        except (elasticsearch5.NotFoundError, elasticsearch.NotFoundError, elasticsearch6.NotFoundError):
            logger.warn(
                "attention! table_id->[%s] can not found any index to update,will do create function", self.table_id
            )
            return self.create_index_v2()

        # 1.1 兼容旧任务，将不合理的超前index清理掉
        # 如果最新时间超前了，要对应处理一下,通常发生在旧任务应用新的es代码过程中
        # 循环处理，以应对预留时间被手动加长,导致超前index有多个的场景
        while now_datetime_object < current_index_info["datetime_object"]:
            logger.warn("table_id->[%s] delete index->[%s] because it has ahead time", self.table_id, last_index_name)
            es_client.indices.delete(index=last_index_name)
            # 重新获取最新的index，这里没做防护，默认存在超前的index，就一定存在不超前的可用index
            current_index_info = self.current_index_info()
            last_index_name = self.make_index_name(
                current_index_info["datetime_object"], current_index_info["index"], current_index_info["index_version"]
            )

        # 2. 判断index是否需要分割
        # 如果是小于分割大小的，不必进行处理
        should_create = False
        if index_size_in_byte / 1024.0 / 1024.0 / 1024.0 > self.slice_size:
            logger.info(
                "table_id->[%s] index->[%s] current_size->[%s] is larger than slice size->[%s], create new index slice",
                self.table_id,
                last_index_name,
                index_size_in_byte,
                self.slice_size,
            )
            should_create = True

        # mapping 不一样了，也需要创建新的index
        if not self.is_mapping_same(last_index_name):
            logger.info(
                "table_id->[%s] index->[%s] mapping is not the same, will create the new",
                self.table_id,
                last_index_name,
            )
            should_create = True

        # 达到保存期限进行分裂
        expired_time_point = self.now - datetime.timedelta(days=self.retention)
        if current_index_info["datetime_object"] < expired_time_point:
            logger.info(
                "table_id->[%s] index->[%s] has arrive retention date, will create the new",
                self.table_id,
                last_index_name,
            )
            should_create = True

        # arrive warm_phase_days date to split index
        # avoid index always not split, it not be allocate to cold node
        if self.warm_phase_days > 0:
            expired_time_point = self.now - datetime.timedelta(days=self.warm_phase_days)
            if current_index_info["datetime_object"] < expired_time_point:
                logger.info(
                    "table_id->[%s] index->[%s] has arrive warm_phase_days date, will create the new",
                    self.table_id,
                    last_index_name,
                )
                should_create = True

        # 2.0 判断新的index信息：日期以及对应的index
        if not should_create:
            logger.info(
                "table_id->[%s] index->[%s] everything is ok,nothing to do",
                self.table_id,
                last_index_name,
            )
            return True

        new_index = 0
        # 判断日期是否当前的时期或时间
        if now_datetime_object.strftime(self.date_format) == current_index_info["datetime_object"].strftime(
            self.date_format
        ):
            # 如果当前index并没有写入过数据(count==0),则对其进行删除重建操作即可
            if es_client.count(index=last_index_name).get("count", 0) == 0:
                new_index = current_index_info["index"]
                es_client.indices.delete(index=last_index_name)
                logger.info(
                    "table_id->[%s] has index->[%s] which has not data, will be deleted for new index create.",
                    self.table_id,
                    last_index_name,
                )
            # 否则原来的index不动，新增一个index，并把alias指向过去
            else:
                new_index = current_index_info["index"] + 1
                logger.info("table_id->[%s] index->[%s] has data, so new index will create", self.table_id, new_index)

        # 但凡涉及到index新增，都使用v2版本的格式
        new_index_name = self.make_index_name(now_datetime_object, new_index, "v2")
        logger.info("table_id->[%s] will create new index->[%s]", self.table_id, new_index_name)

        # 2.1 创建新的index
        es_client.indices.create(index=new_index_name, body=self.index_body, params={"request_timeout": 30})
        logger.info("table_id->[%s] new index_name->[%s] is created now", self.table_id, new_index_name)

        return True

    def clean_index(self):
        """
        清理过期index的操作
        :return: int(清理的index个数) | raise Exception
        """
        # 1. 计算获取当前超时时间节点
        expired_datetime_point = self.now - datetime.timedelta(days=self.retention)
        logger.debug(
            "going to clean table->[{}] es storage index, expired time is->[{}]".format(
                self.table_id, expired_datetime_point.strftime(self.date_format)
            )
        )

        # 2. 获取这个table_id相关的所有index名字
        es_client = self.get_client()
        index_list = es_client.indices.get("{}*".format(self.index_name))
        delete_count = 0

        # 3. 遍历所有的index
        for index_name in list(index_list.keys()):
            # 获取这个index对应的时间内容，并反序列到datetime对象
            result = self.index_re.match(index_name)
            # 如果拿不到正则的匹配成功，需要跳过
            if result is None:
                logger.warning(
                    "table_id->[{}] got index->[{}] which is not match index_re, something go wrong?".format(
                        self.table_id, index_name
                    )
                )
                continue

            # 需要将时间字符串反序列化为datetime object
            datetime_str = result.group("datetime")
            try:
                index_datetime_object = datetime.datetime.strptime(datetime_str, self.date_format)
            except ValueError:
                logger.error(
                    "table_id->[{}] got index->[{}] with datetime_str->[{}] which is not match date_format->"
                    "[{}], something go wrong?".format(self.table_id, index_name, datetime_str, self.date_format)
                )
                continue

            # 判断datetime是否已经小于时间节点
            if index_datetime_object > expired_datetime_point:
                # 未小于，放过他
                logger.info(
                    "table_id->[{}] got index->[{}] which still available, clean later?".format(
                        self.table_id, index_name
                    )
                )
                continue

            # 如果小于时间节点，需要将index清理
            es_client.indices.delete(index_name)
            logger.info(
                "table_id->[{}] now has delete index_name->[{}] for datetime->[{}]".format(
                    self.table_id, index_name, datetime_str
                )
            )
            delete_count += 1

        logging.info("table_id->[{}] clean es index success with count->[{}]".format(self.table_id, delete_count))
        return delete_count

    def get_alias_datetime_str(self, alias_name):
        # 判断是否是需要的格式
        # write_xxx
        alias_write_re = self.write_alias_re
        # xxx_read
        alias_read_re = self.read_alias_re
        # xxx_write
        old_write_alias_re = self.old_write_alias_re

        # 匹配并获取时间字符串
        write_result = alias_write_re.match(alias_name)
        if write_result is not None:
            return write_result.group("datetime")
        read_result = alias_read_re.match(alias_name)
        if read_result is not None:
            return read_result.group("datetime")
        old_write_result = old_write_alias_re.match(alias_name)
        if old_write_result is not None:
            return old_write_result.group("datetime")
        return ""

    def clean_index_v2(self):
        """
        清理过期的写入别名及index的操作，如果发现某个index已经没有写入别名，那么将会清理该index
        :return: int(清理的index个数) | raise Exception
        """
        # 没有快照任务可以直接删除
        # 有快照任务需要判断是否可以删除
        if not self.can_delete():
            return
        # 获取所有的写入别名
        es_client = self.get_client()

        alias_list = es_client.indices.get_alias(index=f"*{self.index_name}_*_*")

        filter_result = self.group_expired_alias(alias_list, self.retention)

        for index_name, alias_info in filter_result.items():
            # 回溯的索引不经过正常删除的逻辑删除
            if index_name.startswith(self.restore_index_prefix):
                continue
            if alias_info["not_expired_alias"]:
                if alias_info["expired_alias"]:
                    # 如果存在已过期的别名，则将别名删除
                    logger.info(
                        "table_id->[%s] delete_alias_list->[%s] is not empty will delete the alias.",
                        self.table_id,
                        alias_info["expired_alias"],
                    )
                    es_client.indices.delete_alias(index=index_name, name=",".join(alias_info["expired_alias"]))
                    logger.warning(
                        "table_id->[%s] delete_alias_list->[%s] is deleted.",
                        self.table_id,
                        alias_info["expired_alias"],
                    )
                continue
            # 如果已经不存在未过期的别名，则将索引删除
            # 等待所有别名过期删除索引，防止删除别名快照时，丢失数据
            logger.info(
                "table_id->[%s] has not alias need to keep, will delete the index->[%s].",
                self.table_id,
                index_name,
            )
            try:
                es_client.indices.delete(index=index_name)
            except (
                elasticsearch5.ElasticsearchException,
                elasticsearch.ElasticsearchException,
                elasticsearch6.ElasticsearchException,
            ):
                logger.warning(
                    "table_id->[%s] index->[%s] delete failed, index maybe doing snapshot", self.table_id, index_name
                )
                continue
            logger.warning("table_id->[%s] index->[%s] is deleted now.", self.table_id, index_name)

        logger.info("table_id->[%s] is process done.", self.table_id)

        return True

    def is_mapping_same(self, index_name):
        """
        判断一个index的mapping和数据库当前记录的配置是否一致
        :param index_name: 当前的时间字符串
        :return: {
            # 是否需要创建新的索引
            "should_create": True | False,
            # 新的索引名
            "index": "index_name",
            # 新索引对应的写别名
            "write_alias": "write_alias"
        }
        """
        es_client = self.get_client()

        # 判断最后一个index的配置是否和数据库的一致，如果不是，表示需要重建
        try:
            es_mappings = es_client.indices.get_mapping(index=index_name)[index_name]["mappings"]
            current_mapping = {}
            if es_mappings.get(self.table_id):
                current_mapping = es_mappings[self.table_id]["properties"]
            else:
                current_mapping = es_mappings["properties"]

        except (KeyError, elasticsearch5.NotFoundError, elasticsearch.NotFoundError, elasticsearch6.NotFoundError):
            logger.info("index_name->[{}] is not exists, will think the mapping is not same.".format(index_name))
            return False

        # 判断字段列表是否一致的: _type在ES7.x版本后取消
        if self.es_version < self.ES_REMOVE_TYPE_VERSION:
            es_properties = self.index_body["mappings"][self.table_id]["properties"]
        else:
            es_properties = self.index_body["mappings"]["properties"]
        database_field_list = list(es_properties.keys())
        current_field_list = list(current_mapping.keys())
        # 数据库中字段多于es的index中数据，则进行分裂
        field_diff_set = set(database_field_list) - set(current_field_list)
        if len(field_diff_set) != 0:
            logger.info(
                "table_id->[{}] index->[{}] found differ field->[{}] will thing not same".format(
                    self.table_id, index_name, field_diff_set
                )
            )
            return False

        # 遍历判断字段的内容是否完全一致
        for field_name, database_config in list(es_properties.items()):
            try:
                current_config = current_mapping[field_name]

            except KeyError:
                logger.info(
                    "table_id->[{}] found field->[{}] is missing in current_mapping->[{}], "
                    "will delete it and recreate."
                )
                return False

            # 判断具体的内容是否一致，只要判断具体的四个内容
            for field_config in ["type", "include_in_all", "doc_values", "format"]:
                database_value = database_config.get(field_config, None)
                current_value = current_config.get(field_config, None)

                if field_config == "type" and current_value is None:
                    current_field_properties = current_config.get("properties", None)
                    # object 字段动态写入数据后 不再有type这个字段 只有 properties
                    if current_field_properties and database_value != ResultTableField.FIELD_TYPE_OBJECT:
                        logger.info(
                            "table_id->[{}] index->[{}] field->[{}] config->[{}] database->[{}] es field type is object"
                            "so not same".format(self.table_id, index_name, field_name, field_config, database_value)
                        )
                        return False
                    logger.info(
                        "table_id->[{}] index->[{}] field->[{}] config->[{}] database->[{}] es config is None, "
                        "so nothing will do.".format(
                            self.table_id, index_name, field_name, field_config, database_value
                        )
                    )
                    continue

                if database_value != current_value:
                    logger.info(
                        "table_id->[{}] index->[{}] field->[{}] config->[{}] database->[{}] es->[{}] is "
                        "not the same, ".format(
                            self.table_id, index_name, field_name, field_config, database_value, current_value
                        )
                    )
                    return False

        logger.info("table_id->[{}] index->[{}] field config same.".format(self.table_id, index_name))
        return True

    def get_tag_values(self, tag_name):
        """
        curl -XGET  http://es.service.consul:10004/2_bklog_abcde_20200608_0/_search?pretty -d '
        {
            "aggs" : {
                "field_values" : {
                    "terms" : { "field" : "serverIp", "size":10000 }
                }
            },
            "size" : 0
        }'
        response ==>
        {
            "took" : 301,
            "timed_out" : false,
            "_shards" : {
                "total" : 5,
                "successful" : 5,
                "failed" : 0
            },
            "hits" : {
                "total" : 2124190,
                "max_score" : 0.0,
                "hits" : [ ]
            },
            "aggregations" : {
                "field_values" : {
                    "doc_count_error_upper_bound" : 0,
                    "sum_other_doc_count" : 0,
                    "buckets" : [{
                        "key" : "127.0.0.1",
                        "doc_count" : 2124190
                    }]
                }
            }
        }
        """
        es_client = self.get_client()
        index_list = es_client.indices.get("{}*".format(self.index_name))

        result = []
        for index_name in index_list:
            body = {"aggs": {"field_values": {"terms": {"field": tag_name, "size": 10000}}}, "size": 0}
            res = es_client.search(index=index_name, body=body)
            buckets = res["aggregations"]["field_values"]["buckets"]
            tag_values = [bucket["key"] for bucket in buckets]
            result += tag_values

        return result

    def group_expired_alias(self, alias_list, expired_days):
        """
        将每个索引的别名进行分组，分为已过期和未过期
        :param alias_list: 别名列表，格式
        {
            "2_bkmonitor_event_1500498_20200603_0":{
                "aliases":{
                    "2_bkmonitor_event_1500498_20200603_write":{},
                    "write_20200603_2_bkmonitor_event_1500498":{}
                }
            }
        }
        :param expired_days: 过期时间，单位天
        :return: 格式
        {
            "2_bkmonitor_event_1500498_20200603_0": {
                "expired_alias": ["write_20200603_2_bkmonitor_event_1500498"],
                "not_expired_alias: ["write_20200602_2_bkmonitor_event_1500498"],
            }
        }
        """
        logger.info(
            "table_id->[%s] filtering expired alias before %s days.",
            self.table_id,
            expired_days + ES_ALIAS_EXPIRED_DELAY_DAYS,
        )

        # 按照过期时间进行过期可能导致最早一天的数据查询缺失，让ES别名延迟1天过期，保证数据查询完整
        expired_datetime_point = self.now - datetime.timedelta(days=expired_days + ES_ALIAS_EXPIRED_DELAY_DAYS)

        filter_result = {}

        for index_name, alias_info in alias_list.items():
            # 不处理回溯索引
            if index_name.startswith(self.restore_index_prefix):
                continue

            expired_alias = []
            not_expired_alias = []

            # 遍历所有的alias是否需要删除
            for alias_name in alias_info["aliases"]:
                logger.info("going to process table_id->[%s] ", self.table_id)

                # 判断这个alias是否命中正则，是否需要删除的范围内
                datetime_str = self.get_alias_datetime_str(alias_name)

                if not datetime_str:
                    # 匹配不上时间字符串的情况，一般是因为用户自行创建了别名
                    if settings.ES_RETAIN_INVALID_ALIAS:
                        # 保留不合法的别名，将该别名视为未过期
                        not_expired_alias.append(alias_name)
                        logger.info(
                            "table_id->[%s] index->[%s] got alias_name->[%s] " "not match datetime str, retain it.",
                            self.table_id,
                            index_name,
                            alias_name,
                        )
                    else:
                        # 不保留不合法的别名，将该别名视为已过期
                        expired_alias.append(alias_name)
                        logger.info(
                            "table_id->[%s] index->[%s] got alias_name->[%s] not match datetime str, remove it.",
                            self.table_id,
                            index_name,
                            alias_name,
                        )
                    continue

                try:
                    index_datetime_object = datetime_str_to_datetime(datetime_str, self.date_format, self.time_zone)
                except ValueError:
                    logger.error(
                        "table_id->[%s] got index->[%s] with datetime_str->[%s] which is not match date_format->"
                        "[%s], something go wrong?",
                        self.table_id,
                        index_name,
                        datetime_str,
                        self.date_format,
                    )
                    continue

                # 检查当前别名是否过期
                logger.info("%s %s", index_datetime_object, expired_datetime_point)
                if index_datetime_object > expired_datetime_point:
                    logger.info(
                        "table_id->[%s] got alias->[%s] for index->[%s] is not expired.",
                        self.table_id,
                        alias_name,
                        index_name,
                    )
                    not_expired_alias.append(alias_name)
                else:
                    logger.info(
                        "table_id->[%s] got alias->[%s] for index->[%s] is expired.",
                        self.table_id,
                        alias_name,
                        index_name,
                    )
                    expired_alias.append(alias_name)

            filter_result[index_name] = {
                "expired_alias": expired_alias,
                "not_expired_alias": not_expired_alias,
            }

        return filter_result

    def reallocate_index(self):
        """
        重新分配索引所在的节点
        """
        if self.warm_phase_days <= 0:
            logger.info("table_id->[%s] warm_phase_days is not set, skip.", self.table_id)
            return

        warm_phase_settings = self.warm_phase_settings
        allocation_attr_name = warm_phase_settings["allocation_attr_name"]
        allocation_attr_value = warm_phase_settings["allocation_attr_value"]
        allocation_type = warm_phase_settings["allocation_type"]

        es_client = self.get_client()

        # 获取索引对应的别名
        alias_list = es_client.indices.get_alias(index=f"*{self.index_name}_*_*")

        filter_result = self.group_expired_alias(alias_list, self.warm_phase_days)

        # 如果存在未过期的别名，那说明这个索引仍在被写入，不能把它切换到冷节点
        reallocate_index_list = [
            index_name for index_name, alias in filter_result.items() if not alias["not_expired_alias"]
        ]

        # 如果没有过期的索引，则返回
        if not reallocate_index_list:
            logger.info(
                "table_id->[%s] no index should be allocated, skip.",
                self.table_id,
            )
            return

        ilo = IndexList(es_client, index_names=reallocate_index_list)
        # 过滤掉已经被 allocate 过的 index
        ilo.filter_allocated(key=allocation_attr_name, value=allocation_attr_value, allocation_type=allocation_type)

        # 过滤后索引为空，则返回
        if not ilo.indices:
            logger.info(
                "table_id->[%s] no index should be allocated, skip.",
                self.table_id,
            )
            return

        logger.info(
            "table_id->[%s] ready to reallocate with settings: days(%s), name(%s), value(%s), type(%s), "
            "for index_list: %s",
            self.table_id,
            self.warm_phase_days,
            allocation_attr_name,
            allocation_attr_value,
            allocation_type,
            ilo.indices,
        )

        try:
            # 执行 allocation 动作
            allocation = curator.Allocation(
                ilo=ilo,
                key=allocation_attr_name,
                value=allocation_attr_value,
                allocation_type=allocation_type,
            )
            allocation.do_action()
        except curator.NoIndices:
            # 过滤后索引列表为空，则返回
            if not ilo.indices:
                logger.info(
                    "table_id->[%s] no index should be allocated, skip.",
                    self.table_id,
                )
                return
        except Exception as e:
            logger.exception("table_id->[%s] error occurred when allocate: %s", self.table_id, e)
        else:
            logger.info("table_id->[%s] index->[%s] allocate success!", self.table_id, ilo.indices)

    @property
    def snapshot_date_format(self):
        return "%Y%m%d"

    @property
    def snapshot_re(self):
        pattern = rf"^{self.index_name}_snapshot_(?P<datetime>\d+)$"
        return re.compile(pattern)

    @property
    def search_snapshot(self):
        return f"{self.index_name}_snapshot_*"

    @property
    def can_snapshot(self):
        return self.have_snapshot_conf and self.is_index_enable()

    @property
    def have_snapshot_conf(self):
        return EsSnapshot.objects.filter(table_id=self.table_id).exists()

    @property
    def is_snapshot_stopped(self):
        try:
            obj = EsSnapshot.objects.get(table_id=self.table_id)
            return obj.status == EsSnapshot.ES_STOPPED_STATUS
        except EsSnapshot.DoesNotExist:
            return False

    @property
    def can_delete_snapshot(self):
        es_snapshot: EsSnapshot = EsSnapshot.objects.filter(table_id=self.table_id).first()
        # 永久或者状态是停用的状态，则不允许删除快照数据
        if es_snapshot:
            return not (es_snapshot.is_permanent() or es_snapshot.status == EsSnapshot.ES_STOPPED_STATUS)
        return False

    @cached_property
    def snapshot_obj(self):
        return EsSnapshot.objects.get(table_id=self.table_id)

    @property
    def snapshot_complete_state(self):
        return "SUCCESS"

    @property
    def restore_index_prefix(self):
        return "restore_"

    def can_delete(self) -> bool:
        """
        判断是否可以删除 当存在快照配置当时候需要判断是否可以删除
        - 不快照的结果表 直接删除
        - 当天有索引需要删除的时候 需要判断当天快照是否创建
        - 当天快照完成 删除索引
        """
        if not self.have_snapshot_conf:
            return True

        if not self.can_snapshot:
            return True

        current_snapshot_info = self.current_snapshot_info()
        if self.expired_index():
            if not current_snapshot_info["datetime"]:
                return False
            if current_snapshot_info["datetime"].day != datetime.datetime.utcnow().day:
                return False
        if current_snapshot_info["datetime"]:
            return current_snapshot_info["is_success"]
        return True

    def make_snapshot_name(self, datetime, index):
        return f"{index}_snapshot_{datetime.strftime(self.snapshot_date_format)}"

    def expired_index(self):
        es_client = self.es_client
        alias_list = es_client.indices.get_alias(index=f"*{self.index_name}_*_*")
        expired_index_info = self.group_expired_alias(alias_list, self.retention)
        ret = []

        for expired_index, expired_info in expired_index_info.items():
            if expired_info["not_expired_alias"]:
                continue
            if es_client.count(index=expired_index).get("count", 0) != 0:
                ret.append(expired_index)
        return ret

    def current_snapshot_info(self):
        es_client = self.es_client
        try:
            snapshots = es_client.snapshot.get(
                self.snapshot_obj.target_snapshot_repository_name, self.search_snapshot
            ).get("snapshots", [])
        except (elasticsearch5.NotFoundError, elasticsearch.NotFoundError, elasticsearch6.NotFoundError):
            snapshots = []
        snapshot_re = self.snapshot_re
        max_datetime = None
        max_snapshot = {}

        for snapshot in snapshots:
            snapshot_name = snapshot.get("snapshot")
            re_result = snapshot_re.match(snapshot_name)

            if re_result:
                current_datetime_str = re_result.group("datetime")
                current_datetime = datetime_str_to_datetime(
                    current_datetime_str, self.snapshot_date_format, self.time_zone
                )
                if max_datetime:
                    if current_datetime > max_datetime:
                        max_datetime = current_datetime
                        max_snapshot = snapshot
                    continue

                max_datetime = current_datetime
                max_snapshot = snapshot

        return {
            "datetime": max_datetime,
            "snapshot": max_snapshot.get("snapshot"),
            "is_success": max_snapshot.get("state") == self.snapshot_complete_state,
        }

    def create_snapshot(self):
        if not self.can_snapshot:
            return

        # 如果是停用状态，则不能新建快照
        if self.is_snapshot_stopped:
            return

        es_client = self.es_client
        current_snapshot_info = self.current_snapshot_info()
        now = self.now

        # 如果最新快照不存在 直接创建
        if current_snapshot_info["datetime"]:
            # 当天快照已经创建不再创建
            if current_snapshot_info["datetime"].day == now.day:
                return
            # 快照未完成 不创建新的快照
            if not current_snapshot_info["is_success"]:
                return

        new_snapshot_name = self.make_snapshot_name(now, self.index_name)
        expired_index = self.expired_index()

        # 如果当天没有需要删除的索引 不进行快照
        if not expired_index:
            return
        try:
            with atomic(config.DATABASE_CONNECTION_NAME):
                EsSnapshotIndice.objects.bulk_create(
                    [
                        self.create_target_index_meta_info(_expired_index, new_snapshot_name)
                        for _expired_index in expired_index
                    ]
                )

                es_client.snapshot.create(
                    self.snapshot_obj.target_snapshot_repository_name,
                    new_snapshot_name,
                    {"indices": ",".join(expired_index), "include_global_state": False},
                )
        except Exception as e:
            logger.exception(
                "table_id->[%s] create new snapshot ->[%s] failed e -> [%s]", self.table_id, new_snapshot_name, e
            )
            return

        logger.info("table_id->[%s] has created new snapshot ->[%s]", self.table_id, new_snapshot_name)

    def create_target_index_meta_info(self, index_name, snapshot_name):
        es_client = self.es_client
        create_obj = {
            "table_id": self.table_id,
            "start_time": datetime.datetime.fromtimestamp(
                int(self.__get_last_time_content(index_name).get("time")) / 1000
            ).astimezone(timezone(settings.TIME_ZONE)),
            "end_time": datetime.datetime.fromtimestamp(
                int(self.__get_last_time_content(index_name, False).get("time")) / 1000
            ).astimezone(timezone(settings.TIME_ZONE)),
            "doc_count": es_client.count(index=index_name).get("count"),
            "store_size": es_client.indices.stats(index=index_name, metric="store")["_all"]["primaries"]["store"][
                "size_in_bytes"
            ],
            "cluster_id": self.storage_cluster_id,
            "repository_name": self.snapshot_obj.target_snapshot_repository_name,
            "snapshot_name": snapshot_name,
            "index_name": index_name,
        }
        logger.debug(create_obj)
        return EsSnapshotIndice(**create_obj)

    def __get_last_time_content(self, index, order_asc=True):
        return (
            self.es_client.search(
                index=index, body={"size": 1, "sort": [{"time": {"order": "asc" if order_asc else "desc"}}]}
            )
            .get("hits")
            .get("hits")[0]
            .get("_source")
        )

    def expired_date_timestamp(self, snapshot):
        snapshot_re = self.snapshot_re
        re_result = snapshot_re.match(snapshot)
        snapshot_datetime_str = re_result.group("datetime")
        snapshot_datetime = datetime_str_to_datetime(snapshot_datetime_str, self.snapshot_date_format, self.time_zone)
        expired_datetime_point = snapshot_datetime + datetime.timedelta(days=self.snapshot_obj.snapshot_days)
        return expired_datetime_point.timestamp()

    def get_expired_snapshot(self, expired_days: int):
        logger.info("table_id -> [%s] filter expired snapshot before %s days", self.table_id, expired_days)
        expired_datetime_point = self.now - datetime.timedelta(days=expired_days)

        es_client = self.es_client
        try:
            snapshots = es_client.snapshot.get(
                self.snapshot_obj.target_snapshot_repository_name, self.search_snapshot
            ).get("snapshots", [])
        except (elasticsearch5.NotFoundError, elasticsearch.NotFoundError, elasticsearch6.NotFoundError):
            snapshots = []
        snapshot_re = self.snapshot_re
        expired_snapshots = []

        for snapshot in snapshots:
            snapshot_name = snapshot.get("snapshot")
            re_result = snapshot_re.match(snapshot_name)

            if re_result:
                snapshot_datetime_str = re_result.group("datetime")
                snapshot_datetime = datetime_str_to_datetime(
                    snapshot_datetime_str, self.snapshot_date_format, self.time_zone
                )
                if snapshot_datetime < expired_datetime_point:
                    expired_snapshots.append(snapshot)
        return expired_snapshots

    def clean_snapshot(self):
        if not self.can_delete_snapshot:
            return

        expired_snapshots = self.get_expired_snapshot(self.snapshot_obj.snapshot_days)
        logger.debug("table_id->[%s] need delete snapshot ", self.table_id)

        for expired_snapshot in expired_snapshots:
            snapshot_name = expired_snapshot.get("snapshot")
            try:
                self.delete_snapshot(snapshot_name, self.snapshot_obj.target_snapshot_repository_name)
            except Exception as e:
                logger.exception("clean snapshot => [%s] failed => %s", snapshot_name, e)

        logger.debug("table_id->[%s] has clean snapshot", self.table_id)

    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_snapshot(self, snapshot_name, target_snapshot_repository_name):
        EsSnapshotIndice.objects.filter(table_id=self.table_id, snapshot_name=snapshot_name).delete()
        self.es_client.snapshot.delete(target_snapshot_repository_name, snapshot_name)
        logger.info("table_id -> [%s] has delete snapshot -> [%s]", self.table_id, snapshot_name)

    def delete_all_snapshot(self, target_snapshot_repository_name):
        logger.info("table_id -> [%s] will delete all snapshot", self.table_id)
        all_snapshots = self.es_client.snapshot.get(target_snapshot_repository_name, self.search_snapshot).get(
            "snapshots", []
        )
        for snapshot in all_snapshots:
            snapshot_name = snapshot.get("snapshot")
            try:
                self.delete_snapshot(snapshot_name, target_snapshot_repository_name)
            except Exception as e:
                logger.exception("delete snapshot [%s] failed => %s", snapshot_name, e)
        logger.info("table_id -> [%s] has delete all snapshot", self.table_id)


class DataBusStatus:
    RUNNING = "running"
    STARTING = "starting"


class BkDataStorage(models.Model, StorageResultTable):
    STORAGE_TYPE = ClusterInfo.TYPE_BKDATA

    # 对应ResultTable的table_id
    table_id = models.CharField("结果表名", max_length=128, primary_key=True)

    # 对应计算平台的接入配置ID
    raw_data_id = models.IntegerField("接入配置ID", default=-1)
    etl_json_config = models.TextField("清洗配置")
    bk_data_result_table_id = models.CharField("计算平台的结果表名", max_length=64)

    def __unicode__(self):
        return "{}->{}".format(self.table_id, self.raw_data_id)

    class Meta:
        verbose_name = "bkdata存储配置"
        verbose_name_plural = "bkdata存储配置"

    def get_client(self):
        pass

    def add_field(self, field):
        """
        字段变更的时候需要同步变更计算平台清洗逻辑，以及统计计算节点

        这个变更动作很重，需要放到后台异步任务去执行
        """
        pass

    @property
    def consul_config(self):
        """
        bkdata的storage暂时不需要同步配置到consul，故返回空数据
        """
        return {}

    @classmethod
    def create_table(cls, table_id, is_sync_db=False, is_access_now=False, **kwargs):
        try:
            bkdata_storage = BkDataStorage.objects.get(table_id=table_id)
        except BkDataStorage.DoesNotExist:
            bkdata_storage = BkDataStorage.objects.create(table_id=table_id)

        bkdata_storage.update_storage(is_access_now=is_access_now, **kwargs)

    def update_storage(self, is_access_now=False, **kwargs):
        # 如果立马接入，则在当前进程直接执行，否则走celery异步任务来同步
        if is_access_now:
            self.check_and_access_bkdata()
        else:
            from metadata.task import tasks

            tasks.access_to_bk_data_task.apply_async(args=(self.table_id,), countdown=60)

    def create_databus_clean(self, result_table):
        kafka_storage = KafkaStorage.objects.filter(table_id=result_table.table_id).first()
        if not kafka_storage:
            raise ValueError(_("结果表[{}]数据未写入消息队列，请确认后重试".format(result_table.table_id)))

        # 增加接入部署计划
        topic = kafka_storage.topic
        partition = kafka_storage.partition
        consul_config = kafka_storage.storage_cluster.consul_config

        domain = consul_config.get("cluster_config", {}).get("domain_name")
        port = consul_config.get("cluster_config", {}).get("port")
        # NOTE: kafka broker_url 以实际配置为准，如果没有配置，再使用默认的 broker url
        broker_url = settings.BK_DATA_KAFKA_BROKER_URL
        if domain and port:
            broker_url = "{}:{}".format(domain, port)
        is_sasl = consul_config.get("cluster_config", {}).get("is_ssl_verify")
        user = consul_config.get("auth_info", {}).get("username")
        passwd = consul_config.get("auth_info", {}).get("password")
        # 采用结果表区分消费组
        KAFKA_CONSUMER_GROUP_NAME = gen_bk_data_rt_id_without_biz_id(result_table.table_id)

        # 计算平台要求，raw_data_name不能超过50个字符
        raw_data_name = "{}_{}".format(settings.BK_DATA_RT_ID_PREFIX, result_table.table_id.replace(".", "__"))[-50:]
        params = {
            "data_scenario": "queue",
            "bk_biz_id": settings.BK_DATA_BK_BIZ_ID,
            "description": "",
            "access_raw_data": {
                "raw_data_name": raw_data_name,
                "maintainer": settings.BK_DATA_PROJECT_MAINTAINER,
                "raw_data_alias": result_table.table_name_zh,
                "data_source": "kafka",
                "data_encoding": "UTF-8",
                "sensitivity": "private",
                "description": _("接入配置 ({})").format(result_table.table_name_zh),
                "tags": [],
                "data_source_tags": ["src_kafka"],
            },
            "access_conf_info": {
                "collection_model": {"collection_type": "incr", "start_at": 1, "period": "-1"},
                "resource": {
                    "type": "kafka",
                    "scope": [
                        {
                            "master": broker_url,
                            "group": KAFKA_CONSUMER_GROUP_NAME,
                            "topic": topic,
                            "tasks": partition,
                            "use_sasl": is_sasl,
                            "security_protocol": "SASL_PLAINTEXT",
                            "sasl_mechanism": "SCRAM-SHA-512",
                            "user": user,
                            "password": passwd,
                        }
                    ],
                },
            },
        }
        try:
            result = api.bkdata.access_deploy_plan(**params)
            logger.info("access to bkdata, result:%s", result)

            self.raw_data_id = result["raw_data_id"]
            self.save()
        except Exception:  # noqa
            logger.exception("access to bkdata failed, params:%s", params)
            raise  # 这里继续往外抛出去

    def get_etl_status(self, processing_id):
        """
        根据对应的processing_id获取该清洗任务的状态
        """
        etl_templates = api.bkdata.get_databus_cleans(raw_data_id=self.raw_data_id)
        for etl_template in etl_templates:
            if etl_template["processing_id"] == processing_id:
                return etl_template["status"]

    def check_and_access_bkdata(self):
        """
        1. 先看是否已经接入，没有接入则继续
            第一步：
                - 按kafka逻辑，接入到100147业务下
                - 走access/deploy_plan接口配置kafka接入
                - 走databus/cleans接口配置清洗规则
                - 走databus/tasks接口启动清洗

            第二步：
                - 走auth/tickets接口将100147业务的表授权给某个项目
                - 走dataflow/flow/flows接口创建出一个画布
                - 走dataflow/flow/flows/{flow_id}/nodes/接口创建画布上的实时数据源、统计节点、存储节点
                - 走dataflow/flow/flows/{flow_id}/start/接口启动任务

        2. 已经接入，则走更新逻辑
            - 判断字段是否有变更，无变更则退出，有变更则继续
            - 走access/deploy_plan/{raw_data_id}/接口更新接入计划
            - 走databus/cleans/{processing_id}/接口更新清洗配置
            - 走dataflow/flow/flows/{fid}/nodes/{nid}/接口更新计算节点 & 存储节点
            - 走dataflow/flow/flows/{flow_id}/restart/接口重启任务

        :return:
        """
        try:
            result_table = ResultTable.objects.get(table_id=self.table_id)
        except ResultTable.DoesNotExist:
            raise ValueError(_("结果表%s不存在，请确认后重试") % self.table_id)

        if self.raw_data_id == -1:
            self.create_databus_clean(result_table)

        # 增加或修改清洗配置任务
        json_config, fields = self.generate_bk_data_etl_config()
        etl_json_config = json.dumps(json_config)
        bk_data_rt_id_without_biz_id = gen_bk_data_rt_id_without_biz_id(self.table_id)
        result_table_id = "{}_{}".format(settings.BK_DATA_BK_BIZ_ID, bk_data_rt_id_without_biz_id)
        params = {
            "raw_data_id": self.raw_data_id,
            "json_config": etl_json_config,
            "pe_config": "",
            "bk_biz_id": settings.BK_DATA_BK_BIZ_ID,
            "description": _("清洗配置 ({})").format(result_table.table_name_zh),
            "clean_config_name": _("清洗配置 ({})").format(result_table.table_name_zh),
            "result_table_name": bk_data_rt_id_without_biz_id,
            "result_table_name_alias": result_table.table_name_zh,
            "fields": fields,
        }
        if not self.etl_json_config:
            # 执行创建操作
            try:
                result = api.bkdata.databus_cleans(**params)
            except Exception:  # noqa
                logger.exception("add databus clean to bkdata failed, params:%s", params)
                return
            logger.info("add databus clean to bkdata, result:%s", result)
        else:
            if self.etl_json_config != etl_json_config:
                # 执行更新操作
                try:
                    result = api.bkdata.stop_databus_cleans(result_table_id=result_table_id, storages=["kafka"])
                except Exception:  # noqa
                    logger.exception("stop bkdata databus clean failed, param:%s", params)
                    return
                logger.info("stop bkdata databus clean success, result:%s", result)

                try:
                    params["processing_id"] = result_table_id
                    result = api.bkdata.update_databus_cleans(**params)
                except Exception:  # noqa
                    logger.exception("update databus clean to bkdata failed, params:%s", params)
                    return
                logger.info("update databus clean to bkdata success, result:%s", result)

        # 获取对应的etl任务状态，如果不是running则start三次，如果还不行，则报错
        etl_status = self.get_etl_status(result_table_id)
        if etl_status != DataBusStatus.RUNNING:
            for _i in range(3):
                # 启动清洗任务
                try:
                    result = api.bkdata.start_databus_cleans(result_table_id=result_table_id, storages=["kafka"])
                    # 轮训状态，查看是否启动成功
                    for _k in range(10):
                        status = self.get_etl_status(result_table_id)
                        if status == DataBusStatus.RUNNING:
                            logger.info("start bkdata databus clean success, result:%s", result)
                            break
                        elif status == DataBusStatus.STARTING:
                            time.sleep(1)
                        else:
                            logger.exception("start bkdata databus clean failed, param:%s", params)
                            return
                    else:
                        continue
                    break
                except Exception:  # noqa
                    logger.exception("start bkdata databus clean failed, param:%s", params)
                    return
            else:
                # 启动清洗任务不成功，则报错
                logger.exception("start bkdata databus clean failed, param:%s", params)
                return

            self.etl_json_config = etl_json_config
            self.bk_data_result_table_id = result_table_id
            self.save()

            # 提前做一次授权，授权给某个项目
            auth.ensure_has_permission_with_rt_id(
                settings.BK_DATA_PROJECT_MAINTAINER, result_table_id, int(settings.BK_DATA_PROJECT_ID)
            )

        # filter_unknown_time_with_rt 过滤掉未来时间后再入库
        if self.filter_unknown_time_with_rt():
            self.full_cmdb_node_info_to_result_table()

    def filter_unknown_time_with_rt(self):
        """
        通过dataflow过滤掉未来时间, 同时过滤过去时间后，再进行入库
        """
        from metadata.models.result_table import ResultTableField

        qs = ResultTableField.objects.filter(table_id=self.table_id)
        if not qs.exists():
            return False

        metric_fields = []
        dimension_fields = []
        for field in qs:
            if field.tag in [ResultTableField.FIELD_TAG_DIMENSION, ResultTableField.FIELD_TAG_GROUP]:
                dimension_fields.append(field.field_name)
            elif field.tag in [ResultTableField.FIELD_TAG_METRIC, ResultTableField.FIELD_TAG_TIMESTAMP]:
                metric_fields.append(field.field_name)

        task = FilterUnknownTimeTask(
            rt_id=self.bk_data_result_table_id,
            metric_field=metric_fields,
            dimension_fields=dimension_fields,
        )
        try:
            task.create_flow()
            task.start_flow()
            # 通过轮训去查看该flow的启动状态，如果60s内启动成功则正常返回，如果不成功则报错
            for _i in range(60):
                flow_deploy_info = api.bkdata.get_latest_deploy_data_flow(flow_id=task.data_flow.flow_id)
                if flow_deploy_info.get("status") == "success":
                    logger.info(
                        "create flow({}) successfully, result_id:({})".format(
                            task.flow_name, self.bk_data_result_table_id
                        )
                    )
                    return True
                else:
                    time.sleep(1)
        except Exception as e:  # noqa
            logger.exception(
                "create/start flow({}) failed, result_id:({}), reason: {}".format(
                    task.flow_name, self.bk_data_result_table_id, e
                )
            )
            return False

    def generate_bk_data_etl_config(self):
        from metadata.models.result_table import ResultTableField

        qs = ResultTableField.objects.filter(table_id=self.table_id)
        etl_dimension_assign = []
        etl_metric_assign = []
        etl_time_assign = []
        time_field_name = "time"

        fields = []
        i = 1
        for field in qs:
            if field.tag in [ResultTableField.FIELD_TAG_DIMENSION, ResultTableField.FIELD_TAG_GROUP]:
                fields.append(
                    {
                        "field_name": field.field_name,
                        "field_type": "string",
                        "field_alias": field.description or field.field_name,
                        "is_dimension": True,
                        "field_index": i,
                    }
                )
                etl_dimension_assign.append({"type": "string", "key": field.field_name, "assign_to": field.field_name})
            elif field.tag == ResultTableField.FIELD_TAG_METRIC:
                # 计算平台没有float类型，这里使用double做一层转换
                # 监控的int类型转成计算平台的long类型
                field_type = field.field_type
                if field.field_type == ResultTableField.FIELD_TYPE_FLOAT:
                    field_type = "double"
                elif field.field_type == ResultTableField.FIELD_TYPE_INT:
                    field_type = "long"
                fields.append(
                    {
                        "field_name": field.field_name,
                        "field_type": field_type,
                        "field_alias": field.description or field.field_name,
                        "is_dimension": False,
                        "field_index": i,
                    }
                )
                etl_metric_assign.append({"type": field_type, "key": field.field_name, "assign_to": field.field_name})
            elif field.tag == ResultTableField.FIELD_TAG_TIMESTAMP:
                time_field_name = field.field_name
                fields.append(
                    {
                        "field_name": field.field_name,
                        "field_type": "string",
                        "field_alias": field.description or field.field_name,
                        "is_dimension": False,
                        "field_index": i,
                    }
                )
                etl_time_assign.append({"type": "string", "key": field.field_name, "assign_to": field.field_name})
            else:
                continue

            i += 1

        return (
            {
                "extract": {
                    "args": [],
                    "type": "fun",
                    "label": "label6356db",
                    "result": "json",
                    "next": {
                        "type": "branch",
                        "name": "",
                        "label": None,
                        "next": [
                            {
                                "type": "access",
                                "label": "label5a9c45",
                                "result": "dimensions",
                                "next": {
                                    "type": "assign",
                                    "label": "labelb2c1cb",
                                    "subtype": "assign_obj",
                                    "assign": etl_dimension_assign,
                                    "next": None,
                                },
                                "key": "dimensions",
                                "subtype": "access_obj",
                            },
                            {
                                "type": "access",
                                "label": "label65f2f1",
                                "result": "metrics",
                                "next": {
                                    "type": "assign",
                                    "label": "labela6b250",
                                    "subtype": "assign_obj",
                                    "assign": etl_metric_assign,
                                    "next": None,
                                },
                                "key": "metrics",
                                "subtype": "access_obj",
                            },
                            {
                                "type": "assign",
                                "label": "labelecd758",
                                "subtype": "assign_obj",
                                "assign": etl_time_assign,
                                "next": None,
                            },
                        ],
                    },
                    "method": "from_json",
                },
                "conf": {
                    "timezone": 8,
                    "output_field_name": "timestamp",
                    "time_format": "Unix Time Stamp(seconds)",
                    "time_field_name": time_field_name,
                    "timestamp_len": 10,
                    "encoding": "UTF-8",
                },
            },
            fields,
        )

    def create_statistics_data_flow(self, agg_interval):
        """
        创建好统计的dataflow, 按指定的聚合周期

        实时数据源(数据源节点)  ->  按sql统计聚合(计算节点)  ->  tspider存储（存储节点）

        :param agg_interval: 统计聚合
        :return:
        """
        from metadata.models.result_table import ResultTableField

        qs = ResultTableField.objects.filter(table_id=self.table_id)
        metric_fields = []
        dimension_fields = []
        for field in qs:
            if field.tag in [ResultTableField.FIELD_TAG_DIMENSION, ResultTableField.FIELD_TAG_GROUP]:
                dimension_fields.append(field.field_name)
            elif field.tag == ResultTableField.FIELD_TAG_METRIC:
                metric_fields.append(field.field_name)

        task = StatisticTask(
            rt_id=self.bk_data_result_table_id,
            agg_interval=agg_interval,
            agg_method="MAX",
            metric_field=metric_fields,
            dimension_fields=dimension_fields,
        )
        try:
            task.create_flow()
            task.start_flow()
        except Exception:  # noqa
            logger.exception(
                "create/start flow({}) failed, result_id:({})".format(task.flow_name, self.bk_data_result_table_id)
            )
            return
        logger.info("create flow({}) successfully, result_id:({})".format(task.flow_name, self.bk_data_result_table_id))

    def full_cmdb_node_info_to_result_table(self):
        if not settings.IS_ALLOW_ALL_CMDB_LEVEL:
            return

        from metadata.models.result_table import ResultTableField

        qs = ResultTableField.objects.filter(table_id=self.table_id)
        if not qs.exists():
            return

        metric_fields = []
        dimension_fields = []
        for field in qs:
            if field.tag in [ResultTableField.FIELD_TAG_DIMENSION, ResultTableField.FIELD_TAG_GROUP]:
                dimension_fields.append(field.field_name)
            elif field.tag == ResultTableField.FIELD_TAG_METRIC:
                metric_fields.append(field.field_name)

        task = CMDBPrepareAggregateTask(
            rt_id=to_bk_data_rt_id(self.table_id, settings.BK_DATA_RAW_TABLE_SUFFIX),
            agg_interval=0,
            agg_method="",
            metric_field=metric_fields,
            dimension_fields=dimension_fields,
        )
        try:
            task.create_flow()
            task.start_flow()
        except Exception:  # noqa
            logger.exception(
                "create/start flow({}) failed, result_id:({})".format(task.flow_name, self.bk_data_result_table_id)
            )
            return
        logger.info("create flow({}) successfully, result_id:({})".format(task.flow_name, self.bk_data_result_table_id))


class ArgusStorage(models.Model, StorageResultTable):
    """Argus 存储方案记录, 做数据冷备和降采样使用"""

    STORAGE_TYPE = ClusterInfo.TYPE_ARGUS

    # 对应ResultTable的table_id
    table_id = models.CharField("结果表名", max_length=128, primary_key=True)

    # 对应StorageCluster记录ID
    # 该字段配置，供监控存储外部使用
    storage_cluster_id = models.IntegerField("存储集群")

    tenant_id = models.CharField("argus租户ID", max_length=64)

    def __str__(self):
        return "<{}, {}>".format(self.table_id, self.storage_cluster_id)

    @classmethod
    def create_table(cls, table_id, tenant_id, storage_cluster_id=None, **kwargs):
        """
        实际创建结果表
        :param table_id: 结果表ID
        :param receive_url: argus receive 推送 URL
        :param kwargs: 其余的额外配置，目前无效
        :return: storage object
        """

        # 0. 判断是否需要使用默认集群信息
        if storage_cluster_id is None:
            storage_cluster_id = ClusterInfo.objects.get(
                cluster_type=ClusterInfo.TYPE_ARGUS, is_default_cluster=True
            ).cluster_id

        # 如果有提供集群信息，需要判断
        else:
            if not ClusterInfo.objects.filter(
                cluster_type=ClusterInfo.TYPE_ARGUS, cluster_id=storage_cluster_id
            ).exists():
                logger.error(
                    "cluster_id->[%s] is not exists or is not argus cluster, something go wrong?" % storage_cluster_id
                )
                raise ValueError(_("存储集群配置有误，请确认或联系管理员处理"))

        # 1. 校验table_id， key是否存在冲突
        if cls.objects.filter(table_id=table_id).exists():
            logger.error("result_table->[%s] already has argus storage config, nothing will add." % table_id)
            raise ValueError(_("结果表[%s]配置已存在，请确认后重试") % table_id)

        new_record = cls.objects.create(
            table_id=table_id,
            tenant_id=tenant_id,
            storage_cluster_id=storage_cluster_id,
        )

        logger.info("table->[%s] now has create argus storage config" % table_id)
        return new_record

    @property
    def consul_config(self):
        """返回一个实际存储的consul配置"""

        consul_config = {"storage_config": {"tenant_id": self.tenant_id}}
        # 添加集群信息
        consul_config.update(self.storage_cluster.consul_config)

        # 将存储的修改时间去掉，防止MD5命中失败
        consul_config["cluster_config"].pop("last_modify_time")

        return consul_config

    def get_client(self):
        """获取该结果表的客户端句柄"""
        pass

    def add_field(self, field):
        """增加一个新的字段"""
        pass
