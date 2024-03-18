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

import datetime
import json
import logging
import traceback
import uuid
from typing import Dict, List, Optional, Union

import kafka
import six
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.translation import ugettext as _

from bkmonitor.utils import consul
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config
from metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes
from metadata.utils import consul_tools, hash_util

from .common import Label, OptionBase
from .constants import IGNORED_CONSUL_SYNC_DATA_IDS, IGNORED_STORAGE_CLUSTER_TYPES
from .space import Space, SpaceDataSource
from .storage import (
    ClusterInfo,
    ESStorage,
    InfluxDBStorage,
    KafkaStorage,
    KafkaTopicInfo,
)

ResultTable = None
ResultTableField = None
ResultTableRecordFormat = None
ResultTableOption = None

logger = logging.getLogger("metadata")


class DataSource(models.Model):
    """数据源配置"""

    # 标识 transfer 可以写入的存储表
    TRANSFER_STORAGE_LIST = [ESStorage, InfluxDBStorage, KafkaStorage]

    # 默认使用的MQ类型
    DEFAULT_MQ_TYPE = ClusterInfo.TYPE_KAFKA
    # DATA_LIST列表
    CONSUL_DATA_LIST_PATH = "{}/{}".format(config.CONSUL_PATH, "data_list")

    # 消息队列配置对应关系配置
    MQ_CONFIG_DICT = {ClusterInfo.TYPE_KAFKA: KafkaTopicInfo}

    # 需要指定是纳秒级别的清洗配置内容
    NS_TIMESTAMP_ETL_CONFIG = {"bk_standard_v2_event", "bk_standard_v2_time_series"}

    bk_data_id = models.AutoField("数据源ID", primary_key=True)
    # data_source的token, 用于供各个自定义上报对data_id进行校验，防止恶意上报, 但是对于已有的data_id由于不是自定义，不做处理
    token = models.CharField("上报校验token", max_length=32, default="")
    data_name = models.CharField("数据源名称", max_length=128, db_index=True, unique=True)
    data_description = models.TextField("数据源描述")
    # 对应StorageCluster 记录ID
    mq_cluster_id = models.IntegerField("消息队列集群ID")
    # 对应KafkaTopicInfo 记录ID
    # 后续如果是切换到其他的MQ，可以增加新的消息队列配置表，增加一个data_id对应的mq_type字段
    mq_config_id = models.IntegerField("消息队列配置ID")
    # json格式的记录 或 内容清洗模板的名称
    etl_config = models.TextField("ETL配置")
    is_custom_source = models.BooleanField("是否自定义数据源")
    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    # 标签配置
    # 但是此处将所有的默认值都置为了other，原因是实际这些配置不会用上，在migrations会将标签都修改为符合预期的内容
    # 此处只是为了安慰django migrations
    # 数据类型，表明数据是时序数据、时间数据、事件数据
    type_label = models.CharField(verbose_name="数据类型标签", max_length=128, default=Label.RESULT_TABLE_LABEL_OTHER)
    # 数据源，表明数据是从渠道上来的，可能有bk_monitor, bk_data, custom
    source_label = models.CharField(verbose_name="数据源标签", max_length=128, default=Label.RESULT_TABLE_LABEL_OTHER)
    # 自定义标签信息，供各个信息注入各种自定义内容使用
    # 没有使用description，因为前者是供用户读而用的，提供格式化的数据并不合适
    custom_label = models.CharField(verbose_name="自定义标签信息", max_length=256, default=None, null=True)
    source_system = models.CharField(verbose_name="请求来源的系统", max_length=256, default=settings.SAAS_APP_CODE)
    # 是否启用数据源
    is_enable = models.BooleanField(verbose_name="数据源是否启用", default=True)

    transfer_cluster_id = models.CharField(
        verbose_name="transfer集群ID", default=settings.DEFAULT_TRANSFER_CLUSTER_ID, max_length=50
    )

    is_platform_data_id = models.BooleanField("是否为平台 ID", default=False, help_text="如果为平台级 ID，则认为全量可以访问")
    space_type_id = models.CharField(
        "所属的空间类型",
        max_length=64,
        default=SpaceTypes.ALL.value,
        null=True,
        db_index=True,
        help_text="数据源属于的空间类型，允许授权给对应空间类型",
    )
    space_uid = models.CharField("所属空间的UID", max_length=256, default="")

    class Meta:
        verbose_name = "数据源管理"
        verbose_name_plural = "数据源管理表"

    def __init__(self, *args, **kwargs):
        super(DataSource, self).__init__(*args, **kwargs)
        # just for IDE
        self._mq_cluster = None
        self._mq_config = None

    @staticmethod
    def make_token():
        """生成一个随机的token"""
        return uuid.uuid4().hex

    @property
    def mq_cluster(self):
        """返回数据源的消息队列类型"""
        # 这个配置应该是很少变化的，所以考虑增加缓存
        if getattr(self, "_mq_cluster", None) is None:
            self._mq_cluster = ClusterInfo.objects.get(cluster_id=self.mq_cluster_id)

        return self._mq_cluster

    @property
    def consul_config_path(self):
        """返回当前consul的配置路径"""
        return config.CONSUL_DATA_ID_PATH_FORMAT.format(
            transfer_cluster_id=self.transfer_cluster_id, data_id=self.bk_data_id
        )

    @property
    def consul_fields_path(self):
        """返回当前consul字段的配置路径"""
        return f"{self.consul_config_path}/fields"

    @property
    def mq_config(self):
        """获取data_id对应消息队列的配置信息"""
        if getattr(self, "_mq_config", None) is None:
            self._mq_config = KafkaTopicInfo.objects.get(bk_data_id=self.bk_data_id)

        return self._mq_config

    @property
    def is_custom_timeseries_report(self) -> bool:
        """是否自定义上报的数据源"""
        return self.etl_config in ["bk_standard_v2_time_series"]

    def get_transfer_storage_conf(self, table_id: str) -> List:
        """获取transfer向后端写入的存储的配置"""
        conf_list = []
        for real_storage in self.TRANSFER_STORAGE_LIST:
            try:
                rt_st = real_storage.objects.get(table_id=table_id)
                consul_config = rt_st.consul_config
                # # NOTE: 现阶段 transfer 识别不了 `victoria_metrics`，针对 `victoria_metrics` 类型的存储，跳过写入 consul
                if not consul_config:
                    continue
                if consul_config.get("cluster_type") in IGNORED_STORAGE_CLUSTER_TYPES:
                    continue
                conf_list.append(consul_config)
            except real_storage.DoesNotExist:
                continue

        return conf_list

    def get_spaces_by_data_id(self, bk_data_id: int, from_authorization: Optional[bool] = False) -> Union[List, Dict]:
        """通过数据源 ID 查询空间为授权的或者为当前空间"""
        # 返回来源于授权空间信息
        space_list = list(
            SpaceDataSource.objects.filter(bk_data_id=bk_data_id, from_authorization=from_authorization).values(
                "space_type_id", "space_id"
            )
        )
        # 如果为授权，则直接返回
        if from_authorization:
            return space_list

        # 否则， 返回归属的空间，也就是第一个
        return space_list[0] if space_list else {}

    def clean_cache(self):
        """强行从DB刷新同步数据"""
        self.refresh_from_db()
        self._mq_cluster = None
        self._mq_config = None

    def to_json(self, is_consul_config=False, with_rt_info=True):
        """返回当前data_id的配置字符串"""

        mq_config = {
            "storage_config": {"topic": self.mq_config.topic, "partition": self.mq_config.partition},
            "batch_size": self.mq_config.batch_size,
            "flush_interval": self.mq_config.flush_interval,
            "consume_rate": self.mq_config.consume_rate,
        }
        # 添加集群信息
        mq_config.update(self.mq_cluster.consul_config)
        mq_config["cluster_config"].pop("last_modify_time")

        result_config = {
            "bk_data_id": self.bk_data_id,
            "data_id": self.bk_data_id,
            "mq_config": mq_config,
            "etl_config": self.etl_config,
            "option": DataSourceOption.get_option(self.bk_data_id),
            "type_label": self.type_label,
            "source_label": self.source_label,
            "token": self.token,
            "transfer_cluster_id": self.transfer_cluster_id,
            "data_name": self.data_name,
            "is_platform_data_id": self.is_platform_data_id,
            "space_type_id": self.space_type_id,
            "space_uid": self.space_uid,
        }

        if with_rt_info:
            # 获取ResultTable的配置
            result_table_id_list = [
                info.table_id for info in DataSourceResultTable.objects.filter(bk_data_id=self.bk_data_id)
            ]

            result_table_info_list = []
            # 获取存在的结果表
            real_table_ids = {
                rt["table_id"]: rt
                for rt in ResultTable.objects.filter(
                    table_id__in=result_table_id_list, is_deleted=False, is_enable=True
                ).values("table_id", "bk_biz_id", "schema_type")
            }

            real_table_id_list = list(real_table_ids.keys())
            # 批量获取结果表级别选项
            table_id_option_dict = ResultTableOption.batch_result_table_option(real_table_id_list)
            # 获取字段信息
            table_field_dict = ResultTableField.batch_get_fields(real_table_id_list, is_consul_config)
            # 判断需要未删除，而且在启用状态的结果表
            for rt, rt_info in real_table_ids.items():
                result_table_info_list.append(
                    {
                        "bk_biz_id": rt_info["bk_biz_id"],
                        "result_table": rt,
                        "shipper_list": self.get_transfer_storage_conf(rt),
                        # 如果是自定义上报的情况，不需要将字段信息写入到consul上
                        "field_list": table_field_dict.get(rt, []) if not self.is_custom_timeseries_report else [],
                        "schema_type": rt_info["schema_type"],
                        "option": table_id_option_dict.get(rt, {}),
                    }
                )
            result_config["result_table_list"] = result_table_info_list

        return result_config

    @property
    def gse_route_config(self):
        """
        返回当前data_id在gse的路由配置
        """
        route_name = "stream_to_{}_{}_{}".format(
            config.DEFAULT_GSE_API_PLAT_NAME, self.DEFAULT_MQ_TYPE, self.mq_config.topic
        )
        return {
            "name": route_name,
            "stream_to": {
                "stream_to_id": self.mq_cluster.gse_stream_to_id,
                self.DEFAULT_MQ_TYPE: {
                    "topic_name": self.mq_config.topic,
                    "data_set": six.text_type(self.mq_config.topic[:-1]),
                    "partition": self.mq_config.partition,
                    "biz_id": 0,
                },
            },
        }

    @property
    def is_field_discoverable(self):
        """
        返回该dataSource下覆盖的结果表是否可以支持字段自发现
        :return:
        """
        return self.etl_config == "bk_standard"

    @classmethod
    def refresh_consul_data_list(cls):
        """
        更新consul上data_list列表
        :return: True | False
        """
        # data list 在consul中的作用被废弃，不再使用
        pass

    @classmethod
    def apply_for_data_id_from_gse(cls, operator):
        # 从GSE接口分配dataid
        try:
            params = {
                "metadata": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
                "operation": {"operator_name": operator},
            }
            result = api.gse.add_route(**params)
            return result["channel_id"]
        except BKAPIError:
            logger.exception("从GSE申请ChannelID出错")
            raise

    def _save_space_datasource(
        self, creator: str, space_type_id: str, space_id: str, bk_data_id: str, authorized_spaces: Optional[List] = None
    ):
        """保存空间数据源关系表

        :param creator: 创建者
        :param space_type_id: 空间类型
        :param space_id: 空间英文名称
        :param bk_data_id: 数据源ID
        :param authorized_space: 授权的使用的空间 ID
        """
        # 1. 保存当前空间和数据源的关系
        SpaceDataSource.objects.create(
            creator=creator,
            space_type_id=space_type_id,
            space_id=space_id,
            bk_data_id=bk_data_id,
            from_authorization=False,
        )
        if not authorized_spaces:
            return
        # 2. 授权的空间必须存在
        filter_q = Q()
        for s in authorized_spaces:
            filter_q |= Q(space_type_id=s["space_type_id"], space_id=s["space_id"])
        if Space.objects.filter(filter_q).count() != len(authorized_spaces):
            raise ValueError(_("设置的空间部分不存在"))
        # 3. 创建关联记录
        space_datasource_list = [
            SpaceDataSource(
                creator=creator,
                space_type_id=s["space_type_id"],
                space_id=s["space_id"],
                bk_data_id=bk_data_id,
                from_authorization=True,
            )
            for s in authorized_spaces
        ]
        SpaceDataSource.objects.bulk_create(space_datasource_list)

    @classmethod
    def create_data_source(
        cls,
        data_name,
        etl_config,
        operator,
        source_label,
        type_label,
        bk_data_id=None,
        mq_cluster=None,
        mq_config=None,
        data_description="",
        is_custom_source=True,
        is_refresh_config=True,
        custom_label=None,
        option=None,
        transfer_cluster_id=None,
        source_system=settings.SAAS_APP_CODE,
        space_type_id=None,
        space_id=None,
        is_platform_data_id=False,
        authorized_spaces=None,
        space_uid=None,
    ):
        """
        创建一个新的数据源, 如果创建过程失败则会抛出异常
        :param transfer_cluster_id: transfer 集群ID，默认为 default
        :param data_name: 数据源名称
        :param bk_data_id: 数据源ID，如果未None则自增配置
        :param mq_cluster: Kafka 集群ID，如果为None时，则使用默认的Kafka集群
        :param mq_config: Kafka 集群配置 {"topic": "xxxx", "partition": 1}
        :param etl_config: 清洗配置，可以为json格式字符串，或者默认内置的清洗配置函数名
        :param operator: 操作者
        :param source_label: 数据源标签
        :param type_label: 数据类型标签
        :param is_custom_source: 是否自定义数据源
        :param data_description: 数据源描述
        :param is_refresh_config: 是否需要刷新外部依赖配置
        :param custom_label: 自定义标签配置信息
        :param option: 额外配置项，格式应该为字典（object）方式传入，key为配置项，value为配置内容
        :param source_system: 来源注册系统
        :param space_type_id: 空间类型
        :param space_id: 空间ID
        :param is_platform_data_id: 是否为平台级 ID
        :param authorized_spaces: 授权使用的空间ID
        :param space_uid: 空间 UID
        :return: DataSource instance | raise Exception
        """
        # 判断两个使用到的标签是否存在
        if not Label.exists_label(label_id=source_label, label_type=Label.LABEL_TYPE_SOURCE) or not Label.exists_label(
            label_id=type_label, label_type=Label.LABEL_TYPE_TYPE
        ):
            logger.error(
                "user->[{}] try to create datasource but use type_label->[{}] or source_type->[{}] "
                "which is not exists.".format(operator, type_label, source_label)
            )
            raise ValueError(_("标签[{} | {}]不存在，请确认后重试").format(source_label, type_label))

        # 1. 判断参数是否符合预期
        # 数据源名称是否重复
        if cls.objects.filter(data_name=data_name).exists():
            logger.error("data_name->[%s] is already exists, maybe something go wrong?" % data_name)
            raise ValueError(_("数据源名称[%s]已经存在，请确认后重试") % data_name)

        try:
            # 如果集群信息无提供，则使用默认的MQ集群信息
            if mq_cluster is None:
                mq_cluster = ClusterInfo.objects.get(cluster_type=cls.DEFAULT_MQ_TYPE, is_default_cluster=True)
            else:
                mq_cluster = ClusterInfo.objects.get(cluster_id=mq_cluster)
        except ClusterInfo.DoesNotExist:
            # 此时，用户无提供新的数据源配置的集群信息，而也没有配置默认的集群信息，新的数据源无法配置集群信息
            # 需要抛出异常
            logger.error(
                "failed to get default MQ for cluster type->[%s], maybe admin set something wrong?"
                % cls.DEFAULT_MQ_TYPE
            )
            raise ValueError(_("缺少数据源MQ集群信息，请联系管理员协助处理"))

        if bk_data_id is None and settings.IS_ASSIGN_DATAID_BY_GSE:
            # 如果由GSE来分配DataID的话，那么从GSE获取data_id，而不是走数据库的自增id
            bk_data_id = cls.apply_for_data_id_from_gse(operator)

        # TODO: 通过空间及类型获取默认管道
        space_type_id = space_type_id if space_type_id else SpaceTypes.ALL.value

        # 此处启动DB事务，创建默认的信息
        with atomic(config.DATABASE_CONNECTION_NAME):
            if transfer_cluster_id is None:
                transfer_cluster_id = settings.DEFAULT_TRANSFER_CLUSTER_ID

            # 3. 创建新的实例及数据源配置
            # 注意：此处由于已经开启事务，MySQL会保留PK给该新实例，因此可以放心将该PK传给其他依赖model
            data_source = cls.objects.create(
                bk_data_id=bk_data_id,
                data_name=data_name,
                etl_config=etl_config,
                creator=operator,
                mq_cluster_id=mq_cluster.cluster_id,
                is_custom_source=is_custom_source,
                data_description=data_description,
                # 由于mq_config和data_source两者相互指向对方，所以只能先提供占位符，先创建data_source
                mq_config_id=0,
                last_modify_user=operator,
                source_label=source_label,
                type_label=type_label,
                custom_label=custom_label,
                source_system=source_system,
                # 生成token
                token=cls.make_token(),
                is_enable=True,
                transfer_cluster_id=transfer_cluster_id,
                is_platform_data_id=is_platform_data_id,
                # 如果空间类型为空，则默认为 all
                space_type_id=space_type_id,
            )

            # 由监控自己分配的dataid需要校验是否在合理的范围内
            if not settings.IS_ASSIGN_DATAID_BY_GSE:
                # 判断DATA_ID是否有问题
                if data_source.bk_data_id < config.MIN_DATA_ID:
                    # 如果小于的最小的data_id，需要判断最小ID是否已经分配了，如果没有分配，则使用之
                    if cls.objects.filter(bk_data_id=config.MIN_DATA_ID).exists():
                        logger.info(
                            "new data_id->[%s] and min data_id is exists, maybe something go wrong?"
                            % data_source.bk_data_id
                        )
                        raise ValueError(_("数据源ID生成异常，请联系管理员协助处理"))

                    # 表示不存在最小的ID，使用之
                    # 但在替换DATA_ID之前，需要先将已有的记录清理，否则对于django操作会有两条记录
                    data_source.delete()
                    data_source.bk_data_id = config.MIN_DATA_ID
                    data_source.save()

                # 达到了最大值的判断
                if data_source.bk_data_id > config.MAX_DATA_ID:
                    logger.info(
                        "new data_id->[%s] is lager than max data id->[%s], nothing will create."
                        % data_source.bk_data_id,
                        config.MAX_DATA_ID,
                    )
                    raise ValueError(_("数据源ID分配达到最大上限，请联系管理员协助处理"))

            logger.info(
                "data_id->[{}] data_name->[{}] by operator->[{}] now is pre-create.".format(
                    data_source.bk_data_id, data_source.data_name, data_source.creator
                )
            )

            # 获取这个数据源对应的配置记录model，并创建一个新的配置记录
            if not mq_config:
                mq_config = {}
            mq_config = cls.MQ_CONFIG_DICT[mq_cluster.cluster_type].create_info(
                bk_data_id=data_source.bk_data_id, **mq_config
            )
            data_source.mq_config_id = mq_config.id
            data_source.save()
            logger.info(
                "data_id->[%s] now is relate to its mq config id->[%s]"
                % (data_source.bk_data_id, data_source.mq_config_id)
            )

            if space_uid:
                # 校验 space_uid 格式
                try:
                    space_type_id, space_id = space_uid.split(SPACE_UID_HYPHEN)
                    data_source.space_uid = space_uid
                    data_source.save()
                    logger.info(
                        "data_id->[{}] now set space uid->[{}]".format(data_source.bk_data_id, data_source.space_uid)
                    )
                except ValueError:
                    raise ValueError(_("空间唯一标识{}错误").format(space_uid))

            # 创建option配置
            option = {} if option is None else option
            # 添加允许指标为空时，丢弃记录选项
            option.update({DataSourceOption.OPTION_DROP_METRICS_ETL_CONFIGS: True})
            for option_name, option_value in list(option.items()):
                DataSourceOption.create_option(
                    bk_data_id=data_source.bk_data_id, name=option_name, value=option_value, creator=operator
                )
                logger.info(
                    "bk_data_id->[{}] now has option->[{}] with value->[{}]".format(
                        data_source.bk_data_id, option_name, option_value
                    )
                )

            # 添加时间 option
            cls._add_time_unit_options(operator, data_source.bk_data_id, etl_config)

        # 写入 空间与数据源的关系表，如果 data id 为全局不需要记录
        try:
            if not is_platform_data_id and space_type_id and space_id:
                cls()._save_space_datasource(operator, space_type_id, space_id, bk_data_id, authorized_spaces)
        except Exception:
            logger.exception("save the relationship for space and datasource error")

        # 5. 触发consul刷新, 只有提交了事务后，其他人才可以看到DB记录
        if is_refresh_config:
            try:
                data_source.refresh_outer_config()
                logger.info("data_id->[%s] refresh consul and outer_config done. " % data_source.bk_data_id)

            except Exception:
                logger.error(
                    "data_id->[%s] refresh outer_config failed for->[%s] will wait cron task to finish."
                    % (data_source.bk_data_id, traceback.format_exc())
                )

        logger.info("data->[%s] now IS READY, TRY IT~" % data_source.bk_data_id)

        # 6. 返回新实例
        return data_source

    @classmethod
    def _add_time_unit_options(cls, operator: str, bk_data_id: int, etl_config: str):
        """添加时间相关 option"""
        # 判断是否NS支持的etl配置，如果是，则需要追加option内容
        # NOTE: 这里实际的时间单位为 ms, 为防止其它未预料问题，其它类型单独添加为毫秒
        if etl_config in cls.NS_TIMESTAMP_ETL_CONFIG:
            DataSourceOption.create_option(
                bk_data_id=bk_data_id,
                name=DataSourceOption.OPTION_TIMESTAMP_UNIT,
                value="ms",
                creator=operator,
            )
            logger.info(
                "bk_data_id->[%s] etl_config->[%s] so is has now has option->[%s] with value->[ms]",
                bk_data_id,
                etl_config,
                DataSourceOption.OPTION_TIMESTAMP_UNIT,
            )
        else:
            # 时间单位统一为毫秒
            DataSourceOption.create_option(
                bk_data_id=bk_data_id,
                name=DataSourceOption.OPTION_ALIGN_TIME_UNIT,
                value="ms",
                creator=operator,
            )
            logger.info(
                "bk_data_id->[%s] has time unit option->[%s] with value->[ms]",
                bk_data_id,
                DataSourceOption.OPTION_ALIGN_TIME_UNIT,
            )

    def update_config(
        self,
        operator,
        data_name=None,
        mq_cluster_id=None,
        etl_config=None,
        data_description=None,
        option=None,
        is_enable=None,
        is_platform_data_id=None,
        authorized_spaces=None,
        space_type_id=None,
        space_uid=None,
    ):
        """
        更新一个数据源的配置，操作成功将会返回True 否则 抛出异常
        :param operator: 操作者
        :param data_name: 数据源名称
        :param mq_cluster_id: 集群ID
        :param etl_config: 清洗配置修改
        :param data_description: 数据源描述
        :param option: 额外配置项，格式应该为字典（object）方式传入，key为配置项，value为配置内容
        :param is_enable: 是否启用数据源
        :param space_type_id: 空间类型
        :param space_uid: 空间 uid
        :return: True | raise Exception
        """

        # 1. 增加标志位，判断是否有修改成功的记录
        is_change = False

        # 2. 判断和修改请求内容，注意判断修改的内容是否合理
        # 2.1 etl_config的配置是否符合要求
        if etl_config is not None:
            self.etl_config = etl_config
            logger.info("data_id->[{}] got new etl_config->[{}]".format(self.bk_data_id, etl_config))
            is_change = True

        # 2.2 mq_cluster_id集群修改
        if mq_cluster_id is not None:
            # 是否存在，集群配置是否合理
            if not ClusterInfo.objects.filter(cluster_id=mq_cluster_id).exists():
                logger.error("cluster_id->[{}] is not exists, nothing will update.".format(mq_cluster_id))
                raise ValueError(_("集群配置不存在，请确认"))

            self.mq_cluster_id = mq_cluster_id
            logger.info("data_id->[{}] now is point to new cluster_id->[{}]".format(self.bk_data_id, mq_cluster_id))
            is_change = True

        # 2.3 data_name判断是否需要修改
        # 需要提供了data_name，而且data_name与当前的data_name不是一个东东
        if data_name is not None and self.data_name != data_name:
            if self.__class__.objects.filter(data_name=data_name).exists():
                logger.error(
                    "user->[{operator}] try to update data_id->{data_id}] data_name->[{data_name}] "
                    "but data name is already exists, nothing will do".format(
                        operator=operator, data_id=self.bk_data_id, data_name=data_name
                    )
                )
                raise ValueError(_("数据源名称已存在，请确认"))
            self.data_name = data_name
            is_change = True

        # 2.4 修改数据源的描述
        if data_description is not None:
            self.data_description = data_description
            logger.info("data_id->[{}] set new data_description.".format(self.bk_data_id))
            is_change = True

        if option is not None:
            # 更新option配置
            for option_name, option_value in list(option.items()):
                DataSourceOption.create_or_update(
                    bk_data_id=self.bk_data_id, name=option_name, value=option_value, creator=operator
                )
                logger.info(
                    "bk_data_id->[{}] now has option->[{}] with value->[{}]".format(
                        self.bk_data_id, option_name, option_value
                    )
                )

        # 2.5 判断是否需要修改启用标记位
        if is_enable is not None:
            consul_client = consul.BKConsul()

            self.is_enable = is_enable
            logger.info("data_id->[{}] now set is_enable->[{}]".format(self.bk_data_id, self.is_enable))
            is_change = True

            # 判断是否is_enable变为了False(数据源禁用)，如果是则需要同时清理consul配置，告知transfer停止写入
            if not is_enable:
                consul_client.kv.delete(self.consul_config_path)
                logger.info("datasource->[%s] now is deleted its consul path." % self.bk_data_id)

        # 2.6 更新数据源针对空间的配置
        if is_platform_data_id is not None:
            self.is_platform_data_id = is_platform_data_id
            logger.info("data_id: %d update is_platform_data_id: %s", self.bk_data_id, is_platform_data_id)
            is_change = True

        # 2.7 如果空间类型不为空时，则更新属性
        if space_type_id is not None:
            self.space_type_id = space_type_id
            logger.info("data_id: %d update space_type_id: %s", self.bk_data_id, space_type_id)
            is_change = True

        # 2.8 如果空间 uid 不为空时，更新
        if space_uid is not None:
            self.space_uid = space_uid
            logger.info("data_id: %d update space_uid: %s", self.bk_data_id, space_uid)
            is_change = True

        # 3. 如果有成功修改，提交修改
        if is_change:
            # 修改后更新ZK配置 和 consul配置
            self.last_modify_user = operator
            self.save()
            self.refresh_consul_config()
            self.refresh_gse_config()
            logger.info("data_id->[%s] update success and notify zk & consul success." % self.bk_data_id)

        if authorized_spaces is not None:
            # 写入 空间与数据源的关系表
            space_info = self.get_spaces_by_data_id(self.bk_data_id)
            if space_info:
                try:
                    self._save_space_datasource(
                        operator,
                        space_info["space_type_id"],
                        space_info["space_id"],
                        self.bk_data_id,
                        authorized_spaces,
                    )
                except Exception:
                    logger.exception("save the relationship for space and datasource error")

        return True

    def refresh_gse_config(self):
        """
        刷新GSE 配置，告知GSE DATA服务最新的MQ配置信息
        :return: True | raise Exception
        """
        self.refresh_gse_config_to_gse()

    def add_built_in_channel_id_to_gse(self):
        if not config.is_built_in_data_id(self.bk_data_id):
            return

        logger.warning("try to add register built_in channel_id({}) to gse".format(self.bk_data_id))
        params = {
            "metadata": {"channel_id": self.bk_data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": settings.COMMON_USERNAME},
            "route": [self.gse_route_config],
        }
        result = api.gse.add_route(**params)
        return result.get("channel_id", -1) == self.bk_data_id

    def refresh_gse_config_to_gse(self):
        """同步路由配置到gse"""
        if self.mq_cluster.gse_stream_to_id == -1:
            raise ValueError(_("dataid({})的消息队列未初始化，请联系管理员处理").format(self.bk_data_id))

        params = {
            "condition": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": self.bk_data_id},
            "operation": {"operator_name": settings.COMMON_USERNAME},
        }
        try:
            result = api.gse.query_route(**params)
            if not result:
                logger.error("can not find route info from gse, please check your datasource config")
                return
        except BKAPIError as e:
            logger.exception("query gse route failed, error:({})".format(e))
            self.add_built_in_channel_id_to_gse()
            return

        old_route = None
        for route_info in result:
            if old_route:
                break

            stream_to_info_list = route_info.get("route", [])
            if not stream_to_info_list:
                continue

            for stream_to_info in stream_to_info_list:
                route_name = stream_to_info.get("name", "")
                if route_name != self.gse_route_config["name"]:
                    continue

                old_route = {"name": route_name, "stream_to": stream_to_info["stream_to"]}
                break

        # 有的话，先比对是否一致
        old_hash = hash_util.object_md5(old_route)
        new_hash = hash_util.object_md5(self.gse_route_config)
        if old_hash == new_hash:
            return

        logger.debug(
            "data_id->[{}] gse route config->[{}] is different from gse->[{}],"
            " will refresh it.".format(self.bk_data_id, new_hash, old_hash)
        )

        params = {
            "condition": {"channel_id": self.bk_data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": self.creator},
            "specification": {"route": [self.gse_route_config]},
        }
        api.gse.update_route(**params)
        logger.info("data_id->[%s] success to push route info to gse" % self.bk_data_id)

    def delete_consul_config(self, consul_config_path=""):
        consul_config_path = consul_config_path or self.consul_config_path
        # 获取consul的句柄
        hash_consul = consul_tools.HashConsul()
        # 删除旧dataid的配置
        hash_consul.delete(consul_config_path)
        logger.info("dataid->[%d] has delete config from->[%s]" % (self.bk_data_id, consul_config_path))

    def redirect_consul_config(self, new_transfer_cluster_id):
        """
        重定向consul上对应节点的配置
        :return: True | raise Exception
        """
        # 暂存旧的prefix
        old_transfer_cluster_id = self.transfer_cluster_id
        if old_transfer_cluster_id == new_transfer_cluster_id:
            logger.info(
                "dataid->[%d] get new transfer cluster id which is same as old->[%s] nothing to do",
                self.bk_data_id,
                old_transfer_cluster_id,
            )
            return

        # 删除旧consul数据
        self.delete_consul_config()

        # 更新为新路径
        self.transfer_cluster_id = new_transfer_cluster_id

        # 将数据库修改存储起来
        self.save()

        # 刷新consul数据
        self.refresh_consul_config()

        logger.info(
            "data_id->[%s] redirect config from ->[%s] to ->[%s] success",
            self.bk_data_id,
            old_transfer_cluster_id,
            new_transfer_cluster_id,
        )

    def refresh_consul_config(self):
        """
        更新consul配置，告知ETL等其他依赖模块配置有所更新
        :return: True | raise Exception
        """
        # 如果数据源没有启用，则不用刷新 consul 配置
        if not self.is_enable:
            return

        # transfer不处理data_id 1002--1006的数据，忽略推送到consul
        if self.bk_data_id in IGNORED_CONSUL_SYNC_DATA_IDS:
            logger.info("data_id->[{}] update config to consul skip.".format(self.bk_data_id))
            return

        # 1. 获取consul的句柄
        hash_consul = consul_tools.HashConsul()

        # 2. 刷新当前data_id的配置
        hash_consul.put(
            key=self.consul_config_path, value=self.to_json(is_consul_config=True), bk_data_id=self.bk_data_id
        )
        logger.info(
            "data_id->[{}] has update config to ->[{}] success".format(self.bk_data_id, self.consul_config_path)
        )

    def create_mq(self):
        """
        初始化准备消息队列环境，预期中获取消息队列的配置，创建之
        :return: True | raise Exception
        """
        kafka_hosts = "{}:{}".format(self.mq_cluster.domain_name, self.mq_cluster.port)
        client = kafka.SimpleClient(hosts=kafka_hosts)
        # 只是确保TOPIC存在，如果不存在则会创建之
        client.ensure_topic_exists("%s" % self.mq_config.topic)
        logger.info("data_id->[{}] now must has topic->[{}]".format(self.bk_data_id, self.mq_config.topic))

    def get_consul_fields(self):
        """
        获取返回consul上的配置信息
        :return: [{
            # 指标字段名称
            "metric":  {
                # 字段类型可有以下选项：
                # int: 整形
                # float: 浮点型
                # string: 字符串
                # timestamp: 时间戳
                "type":"float",
                # 是否由用户配置字段，可能存在字段已自动发现，但未由用户确认
                "is_config_by_user":true,
                # 字段名
                "field_name":"usage",
                "updated_time": "2018-09-09 10:10:10"
            },
            # 组成该条记录的维度字段列表
            "dimension": [{
                # 字段类型可有以下选项：
                # int: 整形
                # float: 浮点型
                # string: 字符串
                # timestamp: 时间戳
                "type":"string",
                # 是否由用户配置字段，可能存在字段已自动发现，但未由用户确认
                "is_config_by_user":true,
                # 字段名
                "field_name":"hostname",
                "updated_time": "2018-09-09 10:10:10"
            }],
            "result_table":  "table_name"
        }]
        """
        consul_client = consul.BKConsul()
        consul_result = consul_client.kv.get(self.consul_fields_path)

        # 如果找不到配置的，不做处理
        if consul_result is None:
            return []

        try:
            result = json.load(consul_result)

        except TypeError:
            return []

        return result

    def update_field_config(self):
        """
        更新结果表的字段配置信息
        :return: True | raise Exception
        """
        # 确认必须是可以更新字段的datasource
        if not self.is_field_discoverable:
            logger.info("data_id->[%s] is not self discoverable, nothing will update ." % self.bk_data_id)
            return True

        consul_fields = self.get_consul_fields()

        for table_config in consul_fields:
            table_id = table_config["result_table"]
            metric_name = table_config["metric"]["field_name"]
            dimension_list = [dimension_field["field_name"] for dimension_field in table_config["dimension"]]

            # 判断是否已经存在字段配置
            if ResultTableRecordFormat.objects.filter(
                table_id=table_id, metric=metric_name, dimension_list=json.dumps(dimension_list)
            ).exists():
                logger.info(
                    "record format for table->[%s] metric->[%s] dimension->[%s] is exists, nothing will do."
                    % (table_id, metric_name, dimension_list)
                )
                continue

            # 如果不存在，需要先创建所有的字段，然后创建record_format
            for dimension_field in table_config["dimension"]:
                if not ResultTableField.objects.filter(
                    table_id=table_id, field_name=dimension_field["field_name"]
                ).exists():
                    ResultTableField.create_field(
                        table_id=table_id,
                        field_name=dimension_field["field_name"],
                        field_type=dimension_field["type"],
                        is_config_by_user=False,
                        operator="system",
                        tag="dimension",
                    )

            if not ResultTableField.objects.filter(
                table_id=table_id, field_name=table_config["metric"]["field_name"]
            ).exists():
                ResultTableField.create_field(
                    table_id=table_id,
                    field_name=table_config["metric"]["field_name"],
                    field_type=table_config["metric"]["type"],
                    is_config_by_user=False,
                    operator="system",
                    tag="metric",
                )

            # 创建record_format记录
            ResultTableRecordFormat.create_record_format(
                table_id=table_id, metric=metric_name, dimension_list=dimension_list
            )
            logger.info("new record for table->[%s] now is create.")

            return True

    def refresh_outer_config(self):
        """
        刷新外部的依赖配置:
        1. GSE 需要写入的MQ创建及准备
        2. GSE的zk配置
        3. Consul的配置
        :return: True | raise Exception
        """
        if not self.is_enable:
            logger.info("data->[%s] is not enable, nothing will refresh to outer systems.", self.bk_data_id)
            return True

        # 刷新GSE的zk配置
        self.refresh_gse_config()
        logger.debug("data_id->[%s] refresh gse config to zk success" % self.bk_data_id)

        # 刷新consul配置
        self.refresh_consul_config()
        logger.debug("data_id->[%s] refresh consul config success." % self.bk_data_id)

        logger.debug("refresh data_id->[%s] all outer config success" % self.bk_data_id)
        return True


class DataSourceOption(OptionBase):
    """数据源配置选项内容"""

    QUERY_NAME = "bk_data_id"

    # 使用本地时间替换数据时间
    OPTION_USE_SOURCE_TIME = "use_source_time"
    # 禁用指标切分
    OPTION_DISABLE_METRIC_CUTTER = "disable_metric_cutter"
    # 允许指标字段缺失
    OPTION_ALLOW_METRICS_MISSING = "allow_metrics_missing"
    # 允许维度字段缺失
    OPTION_ALLOW_DIMENSIONS_MISSING = "allow_dimensions_missing"
    # 记录时间精度
    OPTION_TIME_PRECISION = "time_precision"
    # 增加入库时间指标
    OPTION_INJECT_LOCAL_TIME = "inject_local_time"
    # 入库字段映射改名
    OPTION_ALLOW_USE_ALIAS_NAME = "allow_use_alias_name"
    # GROUP_INFO别名配置
    OPTION_GROUP_INFO_ALIAS = "group_info_alias"
    # 时间单位的配置选项
    OPTION_TIMESTAMP_UNIT = "timestamp_precision"
    # 是否基于指标名切分
    OPTION_IS_SPLIT_MEASUREMENT = "is_split_measurement"
    # 时间单位统一到选项
    OPTION_ALIGN_TIME_UNIT = "align_time_unit"
    # 允许指标为空时，丢弃记录选项, 值为 bool 型
    OPTION_DROP_METRICS_ETL_CONFIGS = "drop_metrics_etl_configs"

    # 增加option标记内容
    bk_data_id = models.IntegerField("数据源ID", db_index=True)
    name = models.CharField(
        "option名称",
        max_length=128,
    )

    @classmethod
    def create_option(cls, bk_data_id, name, value, creator):
        """
        创建结果表字段选项
        :param bk_data_id: 结果表ID
        :param name: 选项名
        :param value: 值
        :param creator: 创建者
        :return:
        """
        if cls.objects.filter(bk_data_id=bk_data_id, name=name).exists():
            logger.error(
                "bk_data_id->[{}] already has option->[{}], maybe something go wrong?".format(bk_data_id, name)
            )
            raise ValueError(_("数据源已存在[{}]选项").format(name))

        # 通过父类统一创建基本信息
        record = cls._create_option(value, creator)

        # 补充子类的特殊信息
        record.bk_data_id = bk_data_id
        record.name = name

        # 写入到数据库
        record.save()

        return record

    @classmethod
    def create_or_update(cls, bk_data_id, name, value, creator):
        """
        创建或者更新结果表字段选项
        :param bk_data_id:  数据源ID
        :param name:   可选字段名称
        :param value:  可选字段值
        :param creator: 创建人和更新人
        :return:
        """
        try:
            record = cls.objects.get(bk_data_id=bk_data_id, name=name)
            val, val_type = cls._parse_value(value)
            record.value = val
            record.value_type = val_type
            record.creator = creator
            record.create_time = datetime.datetime.now()
            record.save()
            return record
        except cls.DoesNotExist:
            # 通过父类统一创建基本信息
            record = cls._create_option(value, creator)

            # 补充子类的特殊信息
            record.bk_data_id = bk_data_id
            record.name = name

            # 写入到数据库
            record.save()
        return record


class DataSourceResultTable(models.Model):
    """数据源与结果表的关系"""

    bk_data_id = models.IntegerField("数据源ID")
    table_id = models.CharField("结果表名", max_length=128)
    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        unique_together = ("bk_data_id", "table_id")
        verbose_name = "数据源-结果表关系配置"
        verbose_name_plural = "数据源-结果表关系配置表"

    def __str__(self):
        return "<{},{}>".format(self.bk_data_id, self.table_id)

    @classmethod
    def modify_table_id_datasource(cls, table_id=None, bk_data_id=None):
        if cls.objects.filter(bk_data_id=bk_data_id).exists():
            raise ValueError(_("数据源有跟结果表关联"))

        if not DataSource.objects.filter(bk_data_id=bk_data_id).exists():
            raise ValueError(_("数据源不存在"))

        refresh_consul_config_data_ids = [bk_data_id]

        with atomic(config.DATABASE_CONNECTION_NAME):
            # 解除老的关联关系
            if cls.objects.filter(table_id=table_id).exists():
                if cls.objects.filter(table_id=table_id).count() != 1:
                    raise ValueError(_("结果表有多个关联数据源"))
                target = cls.objects.filter(table_id=table_id).first()
                logger.info("table_id => [%s] do not relation bk_data_id => [%s]", table_id, target.bk_data_id)
                target.delete()
                refresh_consul_config_data_ids.append(target.bk_data_id)

            cls.objects.create(table_id=table_id, bk_data_id=bk_data_id)

        for datasource in DataSource.objects.filter(bk_data_id__in=refresh_consul_config_data_ids, is_enable=True):
            datasource.refresh_consul_config()

    @classmethod
    def refresh_consul_config_by_table_id(cls, table_id):
        """
        通过 table_id 批量更新 consul 配置
        :param bk_data_id:  数据表id
        :return: None | raise Exception
        """
        data_id_list = list(
            DataSourceResultTable.objects.filter(table_id=table_id).values_list("bk_data_id", flat=True)
        )

        if len(data_id_list) == 0:
            raise ValueError("%s not found" % table_id)

        for datasource in DataSource.objects.filter(bk_data_id__in=data_id_list, is_enable=True):
            datasource.refresh_consul_config()
