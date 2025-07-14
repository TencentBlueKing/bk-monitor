"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import datetime
import json
import logging
import re
import time
import traceback
from typing import Any

from django.conf import settings
from django.db import models, transaction
from django.db.models import sql
from django.db.transaction import atomic, on_commit
from django.utils.translation import gettext as _
from tenacity import retry, stop_after_attempt, wait_exponential

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata import config
from metadata.models.constants import BULK_CREATE_BATCH_SIZE
from metadata.utils.basic import getitems

from .common import BaseModel, Label, OptionBase
from .data_source import DataSource, DataSourceOption, DataSourceResultTable
from .result_table_manage import EnableManager
from .space import SpaceDataSource, SpaceTypeToResultTableFilterAlias
from .space.constants import EtlConfigs, SpaceTypes
from .storage import (
    ArgusStorage,
    BkDataStorage,
    ClusterInfo,
    ESStorage,
    InfluxDBStorage,
    KafkaStorage,
    RedisStorage,
)

logger = logging.getLogger("metadata")


class ResultTable(models.Model):
    """逻辑结果表"""

    CONSUL_INFLUXDB_INFO_PREFIX_PATH = f"{config.CONSUL_PATH}/unify-query/data/influxdb/info"
    CONSUL_INFLUXDB_INFO_VERSION_PATH = f"{config.CONSUL_PATH}/unify-query/version/influxdb/info"
    SCHEMA_TYPE_FREE = "free"
    SCHEMA_TYPE_DYNAMIC = "dynamic"
    SCHEMA_TYPE_FIXED = "fixed"

    SCHEMA_TYPE_CHOICES = (
        (SCHEMA_TYPE_FREE, _("无固定字段")),
        (SCHEMA_TYPE_DYNAMIC, _("动态字段")),
        (SCHEMA_TYPE_FIXED, _("固定字段")),
    )

    # TODO: 多租户 下面所有的存储实体表都需要添加 bk_tenant_id
    REAL_STORAGE_DICT = {
        ClusterInfo.TYPE_ES: ESStorage,
        ClusterInfo.TYPE_INFLUXDB: InfluxDBStorage,
        ClusterInfo.TYPE_REDIS: RedisStorage,
        ClusterInfo.TYPE_KAFKA: KafkaStorage,
        ClusterInfo.TYPE_BKDATA: BkDataStorage,
        ClusterInfo.TYPE_ARGUS: ArgusStorage,
    }

    # 结果表命名规则，应该是DB.TABLE_NAME
    # DB通常是监控范围，例如system, docker, apache等
    # TABLE_NAME是具体指标集合，例如cpu, mem等
    id = models.BigAutoField(primary_key=True)
    table_id = models.CharField("结果表名", db_index=True, max_length=128)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    table_name_zh = models.CharField("结果表中文名", max_length=128)
    is_custom_table = models.BooleanField("是否自定义结果表")
    schema_type = models.CharField("schema配置方案", max_length=64, choices=SCHEMA_TYPE_CHOICES)
    default_storage = models.CharField("默认存储方案", max_length=32, choices=ClusterInfo.CLUSTER_TYPE_CHOICES)
    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    # 业务ID，全业务为0，默认结果表都为全业务表
    bk_biz_id = models.IntegerField("结果表所属业务", default=0)
    # 是否已经禁用的结果表
    is_deleted = models.BooleanField("结果表是否已经禁用", default=False)
    # 是否启用该结果表
    is_enable = models.BooleanField("是否启用", default=True)
    # 数据表标签，默认是其他类型
    label = models.CharField(verbose_name="结果表标签", max_length=128, default=Label.RESULT_TABLE_LABEL_OTHER)
    # 数据标签
    data_label = models.CharField("数据标签", max_length=128, default="", null=True, blank=True)
    is_builtin = models.BooleanField("是否内置", default=False)
    bk_biz_id_alias = models.CharField("业务ID别名", max_length=128, default="", null=True, blank=True)

    class Meta:
        verbose_name = "逻辑结果表"
        verbose_name_plural = "逻辑结果表"
        unique_together = ("table_id", "bk_tenant_id")

    def refresh_datasource(self):
        pass

    @classmethod
    def refresh_consul_influxdb_tableinfo(cls):
        """
        刷新查询模块的table consul配置
        :return: None
        """

        from metadata.utils import consul_tools

        hash_consul = consul_tools.HashConsul()

        # 1. 获取需要刷新的信息列表, 只刷新主力存储是influxdb的结果表
        info_list = cls.objects.filter(default_storage=InfluxDBStorage.STORAGE_TYPE)

        total_count = info_list.count()
        logger.debug(f"total find->[{total_count}] influxdb table info to refresh")

        # 2. 构建需要刷新的字典信息
        refresh_dict = {}
        for table_info in info_list:
            # 如果结果表没有被删除或停用，则需要继续更新路径
            if not table_info.is_deleted and table_info.is_enable:
                refresh_dict[table_info.table_id] = table_info
                continue

            logger.info(
                "table_id->[%s] is disable now, won`t refresh consul data any more and will clean it.",
                table_info.table_id,
            )
            consul_path = "/".join([cls.CONSUL_INFLUXDB_INFO_PREFIX_PATH, table_info.table_id])

            # 同时考虑清理consul上的路径
            if hash_consul.get(consul_path) is not None:
                logger.info(
                    "table_id->[%s] is disable now but consul path exists, will delete the consul path.",
                    table_info.table_id,
                )
                hash_consul.delete(consul_path)

        # 3. 遍历所有的字典信息并写入至consul
        for table_id, table_info in list(refresh_dict.items()):
            consul_path = "/".join([cls.CONSUL_INFLUXDB_INFO_PREFIX_PATH, str(table_id)])

            pivot_table = False
            if table_info.schema_type == ResultTable.SCHEMA_TYPE_FREE:
                if not ResultTable.is_disable_metric_cutter(table_id):
                    pivot_table = True

            segmented_query_enable = False
            option = ResultTableOption.objects.filter(
                table_id=table_id, name=ResultTableOption.OPTION_SEGMENTED_QUERY_ENABLE
            ).first()
            if option:
                segmented_query_enable = option.to_json().get(ResultTableOption.OPTION_SEGMENTED_QUERY_ENABLE, False)

            hash_consul.put(
                key=consul_path,
                value={
                    # 存储是否是行专列
                    "pivot_table": pivot_table,
                    # 分段查询开关
                    "segmented_query_enable": segmented_query_enable,
                    "influxdb_version": "1.7",
                },
            )
            logger.debug(f"consul path->[{consul_path}] is refresh with value->[{refresh_dict}] success.")

        hash_consul.put(key=cls.CONSUL_INFLUXDB_INFO_VERSION_PATH, value={"time": time.time()})

        logger.info(f"all es table info is refresh to consul success count->[{total_count}].")

    @property
    def real_storage_list(self):
        """
        获取结果表的所有实际存储对象
        :return: [real_storage, ]
        """
        result = []
        for storage_str, real_storage in list(self.REAL_STORAGE_DICT.items()):
            try:
                result.append(real_storage.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id))

            except real_storage.DoesNotExist:
                continue

        return result

    @property
    def storage_list(self):
        """
        返回存储的方案字符串列表
        :return: ["influxdb", ]
        """
        result = []
        for storage_str, real_storage in list(self.REAL_STORAGE_DICT.items()):
            if real_storage.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).exists():
                result.append(storage_str)

        return result

    @property
    def data_source(self):
        """
        返回一个结果表的数据源
        :return: DataSource object
        """
        bk_data_id = DataSourceResultTable.objects.get(
            table_id=self.table_id, bk_tenant_id=self.bk_tenant_id
        ).bk_data_id
        return DataSource.objects.get(bk_data_id=bk_data_id, bk_tenant_id=self.bk_tenant_id)

    @classmethod
    def is_disable_metric_cutter(cls, table_id, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        是否 禁用指标切分模式
        """
        data_source_map = DataSourceResultTable.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).first()
        if data_source_map:
            try:
                data_source_option = DataSourceOption.objects.get(
                    bk_data_id=data_source_map.bk_data_id,
                    bk_tenant_id=bk_tenant_id,
                    name=DataSourceOption.OPTION_DISABLE_METRIC_CUTTER,
                )
                return json.loads(data_source_option.value)
            except (DataSourceOption.DoesNotExist, ValueError):
                return False
        return False

    # TODO： 多租户 应该只允许获取一个租户下的结果表
    @classmethod
    def get_table_id_cutter(cls, table_ids: list | set, bk_tenant_id=DEFAULT_TENANT_ID) -> dict:
        """获取结果表是否禁用切分模块"""
        logger.info("get_table_id_cutter: table_ids->[%s],bk_tenant_id->[%s]", table_ids, bk_tenant_id)
        table_id_data_id_map = {
            dr["table_id"]: dr["bk_data_id"]
            for dr in DataSourceResultTable.objects.filter(table_id__in=table_ids).values("table_id", "bk_data_id")
        }
        data_id_option_map = {
            dso["bk_data_id"]: dso["value"]
            for dso in DataSourceOption.objects.filter(
                bk_data_id__in=table_id_data_id_map.values(),
                name=DataSourceOption.OPTION_DISABLE_METRIC_CUTTER,
                bk_tenant_id=bk_tenant_id,
            ).values("bk_data_id", "value")
        }
        # 组装数据
        table_id_cutter = {}
        for table_id in table_ids:
            bk_data_id = table_id_data_id_map.get(table_id)
            # 默认为 False
            if not bk_data_id:
                table_id_cutter[table_id] = False
                continue
            json_option_value = data_id_option_map.get(bk_data_id) or "false"
            try:
                option_value = json.loads(json_option_value)
            except Exception:
                option_value = False
            table_id_cutter[table_id] = option_value

        logger.info(
            "get_table_id_cutter: table_ids->[%s],bk_tenant_id->[%s],result->[%s]",
            table_ids,
            bk_tenant_id,
            table_id_cutter,
        )
        return table_id_cutter

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_result_table(
        cls,
        bk_data_id,
        table_id,
        table_name_zh,
        is_custom_table,
        schema_type,
        operator,
        default_storage,
        bk_tenant_id=DEFAULT_TENANT_ID,
        default_storage_config=None,
        field_list=(),
        is_sync_db=True,
        bk_biz_id=0,
        include_cmdb_level=False,
        label=Label.RESULT_TABLE_LABEL_OTHER,
        external_storage=None,
        is_time_field_only=False,
        option=None,
        time_alias_name=None,
        time_option=None,
        create_storage=True,
        data_label: str | None = None,
        is_builtin=False,
        bk_biz_id_alias=None,
    ):
        """
        创建一个结果表
        :param bk_data_id: 数据源ID
        :param table_id: 结果表ID
        :param table_name_zh: 结果表中文名
        :param is_custom_table: 是否自定义结果表
        :param schema_type: 字段类型
        :param operator: 操作者
        :param label: 结果表标签
        :param default_storage: 默认存储，一个结果表必须存在一个存储，所以创建时需要提供默认存储
        :param bk_tenant_id: 租户ID
        :param default_storage_config: 默认存储创建的对应参数信息, 根据每种不同的存储类型，会有不同的参数传入
        :param field_list: 字段列表，如果是无schema结果表，该参数可以为空
        :param is_sync_db: 是否需要实际创建数据库
        :param bk_biz_id: 结果表所属业务ID
        :param include_cmdb_level: 是否需要创建的默认字段中是否需要带上CMDB层级字段
        :param external_storage: 额外存储配置，格式为{${storage_type}: ${storage_config}}, storage_type可以为kafka等，
            config为具体的配置字典内容
        :param is_time_field_only: 是否仅需要创建时间字段，忽略其他的默认字段；以便兼容日志检索的需求
        :param option: 结果表选项内容
        :param time_alias_name: 时间字段的别名配置
        :param time_option: 时间字段的配置内容
        :param create_storage: 是否创建存储，默认为 True
        :param data_label: 数据标签
        :param is_builtin: 是否为系统内置的结果表
        :param bk_biz_id_alias: 结果表所属业务名称
        :return: result_table instance | raise Exception
        """
        logger.info(
            "create_result_table: start to create result table for bk_data_id->[%s],table_id->[%s],bk_biz_id->[%s],"
            "bk_biz_id_alias->[%s]",
            bk_data_id,
            table_id,
            bk_biz_id,
            bk_biz_id_alias,
        )
        logger.info(
            "create_result_table: start to create result table for bk_tenant_id->[%s],bk_data_id->[%s],"
            "table_id->[%s],bk_biz_id->[%s]",
            bk_tenant_id,
            bk_data_id,
            table_id,
            bk_biz_id,
        )

        # 判断label是否真实存在的配置
        if not Label.exists_label(label_id=label, label_type=Label.LABEL_TYPE_RESULT_TABLE):
            logger.error(
                "create_result_table: user->[%s] try to create rt->[%s] with label->[%s] but is not exists, "
                "nothing will do.",
                operator,
                table_id,
                label,
            )
            raise ValueError(_("标签[{}]不存在，请确认").format(label))

        table_id = table_id.lower()
        # 1. 判断data_source是否存在
        datasource_qs = DataSource.objects.filter(bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id)
        if not datasource_qs.exists():
            logger.error("create_result_table: bk_data_id->[%s] is not exists, nothing will do.", bk_data_id)
            raise ValueError(_("数据源ID不存在，请确认"))
        datasource = datasource_qs.first()
        allow_access_v2_data_link = datasource.etl_config == EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value

        # 非系统创建的结果表，不可以使用容器监控的表前缀名
        if operator != "system" and table_id.startswith(config.BCS_TABLE_ID_PREFIX):
            logger.error(
                "create_result_table: operator->[%s] try to create table->[%s] which is reserved prefix, nothing will "
                "do.",
                operator,
                table_id,
            )
            raise ValueError(_("结果表ID不可以是%s开头，请确认后重试") % config.BCS_TABLE_ID_PREFIX)

        # Q: 为什么不在结果表生成时,在table_id中拼接租户属性，从而做到结果表全局唯一？
        # A: 外部导入的插件,如redis_exporter、mongodb_exporter以及一些内置采集,结果表命名相对固定,使用额外字段过滤更为稳定安全
        if cls.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).exists():
            logger.error(
                "create_result_table: table_id->[%s] in bk_tenant_id->[%s] is already exists, change and try again.",
                table_id,
                bk_tenant_id,
            )
            raise ValueError(_("结果表ID在租户下已经存在，请确认"))

        # TODO: 多租户 是否要变更RT命名标准
        # 校验biz_id是否符合要求
        if str(bk_biz_id) > "0":
            # 如果有指定表的对应业务信息，需要校验结果表的命名是否符合规范
            # 若开启多租户模式，需要获取租户ID
            if settings.ENABLE_MULTI_TENANT_MODE:
                start_string = f"{bk_tenant_id}_{bk_biz_id}_"
            else:  # 若未开启多租户模式，沿用此前的命名规范
                start_string = f"{bk_biz_id}_"

            if not table_id.startswith(start_string):
                logger.error(
                    "create_result_table: user->[%s] try to set table->[%s] under biz->[%s] in bk_tenant_id->[%s] but "
                    "table_id is not start with->[%s], maybe something go wrong?",
                    operator,
                    table_id,
                    bk_biz_id,
                    bk_tenant_id,
                    start_string,
                )
                raise ValueError(_("结果表[%s]不符合命名规范，请确认后重试") % table_id)

        elif str(bk_biz_id) == "0":
            # 全业务的结果表，不可以已数字下划线开头
            if re.match(r"\d+_", table_id):
                logger.error(
                    "create_result_table: user->[%s] try to create table->[%s],bk_tenant_id->[%s]"
                    "which is starts with number, "
                    "but set table under"
                    "biz_id->[0], maybe something go wrong?",
                    operator,
                    table_id,
                    bk_tenant_id,
                )
                raise ValueError(_("全业务结果表不可以数字及下划线开头，请确认后重试"))

        if data_label is None:
            data_label = ""

        # 1.5 新增datasource 的所属空间关联校验
        # 默认归属"bkcc__0"空间
        # 初始值设为传递的值
        target_bk_biz_id = int(bk_biz_id)
        if target_bk_biz_id == 0:
            datasource.is_platform_data_id = True
            datasource.save()
            from .custom_report import EventGroup, TimeSeriesGroup  # noqa

            # TODO: 多租户 关联模型适配租户ID
            if TimeSeriesGroup.objects.filter(bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id).exists():
                # 自定义时序指标，查找所属空间
                target_bk_biz_id = datasource.data_name.split("_")[0]
            elif EventGroup.objects.filter(bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id).exists():
                # 自定义事件，查找所属空间
                target_bk_biz_id = datasource.data_name.split("_")[-1]
            try:
                # 不符合要求的data_name，无法解析业务字段，使用默认全局业务。
                target_bk_biz_id = int(target_bk_biz_id)
            except (ValueError, TypeError):
                target_bk_biz_id = 0
        # 当业务不为 0 时，才进行空间和数据源的关联
        # 因为不会存在部分创建失败的情况，所以，仅在创建时处理即可
        space_type, space_id = None, None
        logger.info(
            "create_result_table: target_bk_biz_id->[%s],table_id->[%s],bk_data_id->[%s]",
            target_bk_biz_id,
            table_id,
            bk_data_id,
        )
        if target_bk_biz_id != 0:
            try:
                from metadata.models import Space

                logger.info(
                    "create_result_table:create space data source, bk_biz_id->[%s], table_id->[%s],"
                    "space_type->[%s], space_id->[%s]",
                    bk_biz_id,
                    table_id,
                    space_type,
                    space_id,
                )
                # 获取空间信息
                # TODO: 多租户，是否补充租户ID
                space = Space.objects.get_space_info_by_biz_id(bk_biz_id=int(target_bk_biz_id))
                # data id 已有所属记录，则不处理（dataid 和 rt 是1对多的关系）
                space_type, space_id = space["space_type"], space["space_id"]
                SpaceDataSource.objects.get_or_create(
                    bk_data_id=bk_data_id,
                    bk_tenant_id=bk_tenant_id,
                    from_authorization=False,
                    defaults={"space_id": space["space_id"], "space_type_id": space["space_type"]},
                )
            except Exception as e:
                logger.error(
                    "create_result_table: create space data source error, target_bk_biz_id type: %s, value: %s, "
                    "bk_tenant_id: %s"
                    "error: %s",
                    type(target_bk_biz_id),
                    target_bk_biz_id,
                    bk_tenant_id,
                    e,
                )

        # 2. 创建逻辑结果表内容
        result_table = cls.objects.create(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            table_name_zh=table_name_zh,
            is_custom_table=is_custom_table,
            schema_type=schema_type,
            default_storage=default_storage,
            creator=operator,
            last_modify_user=operator,
            bk_biz_id=bk_biz_id,
            label=label,
            data_label=data_label,
            is_builtin=is_builtin,
            bk_biz_id_alias=bk_biz_id_alias,
        )

        # TODO: 短期内需要创建SpaceTypeToResultTableFilterAlias记录对应的bk_biz_id_alias,待空间路由整体优化后统一下沉到ResultTable
        if bk_biz_id_alias:
            logger.info(
                "create_result_table: table_id->[%s] need to create filter alias record,bk_biz_id_alias->[%s]",
                table_id,
                bk_biz_id_alias,
            )

            SpaceTypeToResultTableFilterAlias.objects.create(
                table_id=table_id, space_type=SpaceTypes.BKCC.value, filter_alias=bk_biz_id_alias
            )

        # 创建结果表的option内容如果option为非空
        if option is not None:
            ResultTableOption.bulk_create_options(
                table_id=table_id, option_data=option, creator=operator, bk_tenant_id=bk_tenant_id
            )

        # 3. 创建新的字段信息，同时追加默认的字段
        ResultTableField.bulk_create_default_fields(
            table_id=result_table.table_id,
            include_cmdb_level=include_cmdb_level,
            is_time_field_only=is_time_field_only,
            time_alias_name=time_alias_name,
            time_option=time_option,
            bk_tenant_id=bk_tenant_id,
        )

        logger.info(
            "create_result_table: table_id->[%s] ,bk_tenant_id->[%s] "
            "default field is created with include_cmdb_level->[%s]",
            result_table.table_id,
            bk_tenant_id,
            include_cmdb_level,
        )

        # 批量创建 field 数据
        # NOTE: 针对非默认的field，都需要校验字段是否为保留字段
        for new_field in field_list:
            new_field.update(
                {
                    "operator": operator,
                    "is_config_by_user": new_field.get("is_config_by_user", (operator != "system")),
                }
            )
        result_table.bulk_create_fields(field_list, is_etl_refresh=False, is_force_add=True, bk_tenant_id=bk_tenant_id)

        # 4. 创建data_id和该结果表的关系
        DataSourceResultTable.objects.create(
            bk_data_id=bk_data_id, table_id=table_id, creator=operator, bk_tenant_id=bk_tenant_id
        )
        logger.info(
            f"create_result_table: result_table->[{result_table}] now has relate to bk_data->[{bk_data_id}],bk_tenant_id->[{bk_tenant_id}]"
        )

        # 5. 创建实际结果表
        if default_storage_config is None:
            default_storage_config = {}

        # 如果实际创建数据库失败，会有异常抛出，则所有数据统一回滚
        # NOTE: 添加参数标识是否创建存储，以便于可以兼容不需要存储或者已经存在的场景
        if create_storage:
            result_table.check_and_create_storage(
                is_sync_db=is_sync_db,
                external_storage=external_storage,
                option=option,
                default_storage_config=default_storage_config,
                bk_tenant_id=bk_tenant_id,
            )
        # 6. 更新数据写入 consul
        result_table.refresh_etl_config()

        # 7. 针对白名单中的空间及 etl_config 为 `bk_standard_v2_time_series` 的数据源接入 vm
        # 出错时，记录日志，不影响已有功能
        # NOTE: 因为计算平台接口稳定性不可控，暂时放到后台任务执行
        # NOTE: 事务中嵌套异步存在不稳定情况，后续迁移至BMW中进行
        try:
            # TODO： INFLUXDB->VM
            # 仅针对 influxdb 类型进行过滤
            if default_storage == ClusterInfo.TYPE_INFLUXDB:
                # 避免出现引包导致循环引用问题
                from metadata.task.tasks import access_bkdata_vm

                # TODO: 多租户： 等待BkBase多租户接口
                access_bkdata_vm.delay(
                    int(target_bk_biz_id),
                    table_id,
                    datasource.bk_data_id,
                    space_type,
                    space_id,
                    allow_access_v2_data_link,
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("create_result_table: access vm error: %s", e)

        # 因为多个事务嵌套，针对 ES 的操作放在最后执行
        try:
            if default_storage == ClusterInfo.TYPE_ES:
                es_storage = ESStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
                on_commit(lambda: es_storage.create_es_index(is_sync_db=is_sync_db))
        except Exception as e:  # pylint: disable=broad-except
            logger.error("create_result_table: create es storage index error, %s", e)

        return result_table

    def check_and_create_storage(
        self,
        is_sync_db: bool,
        external_storage: dict | None = None,
        option: dict | None = None,
        default_storage_config: dict | None = None,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ) -> bool:
        """检测并创建存储
        NOTE: 针对 influxdb 类型的存储，如果功能开关设置为禁用，则禁用所有新建结果表 influxdb 写入
        """
        storage_enabled = True
        if self.default_storage == ClusterInfo.TYPE_INFLUXDB and not settings.ENABLE_INFLUXDB_STORAGE:
            storage_enabled = False

        if storage_enabled:
            # 当 default_storage_config 值为 None 时，需要设置为 {}
            default_storage_config = default_storage_config or {}
            self.create_storage(
                storage=self.default_storage,
                is_sync_db=is_sync_db,
                bk_tenant_id=bk_tenant_id,
                external_storage=external_storage,
                **default_storage_config,
            )
            logger.info("result_table:[%s] has create storage on type:[%s]", self.table_id, self.default_storage)

    @classmethod
    def get_result_table_storage_info(cls, table_id, storage_type, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        获取结果表一个指定存储的配置信息
        :param table_id: 结果表ID
        :param storage_type: 存储集群配置
        :param bk_tenant_id: 租户ID
        :return: consul config in dict | raise Exception
        """
        storage_class = cls.REAL_STORAGE_DICT[storage_type]
        storage_info = storage_class.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)

        return storage_info.consul_config

    @classmethod
    def get_result_table_storage(cls, table_id, storage_type, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        获取结果表一个指定存储
        :param table_id: 结果表ID
        :param storage_type: 存储集群配置
        :param bk_tenant_id: 租户ID
        :return: consul config in dict | raise Exception
        """
        storage_class = cls.REAL_STORAGE_DICT[storage_type]
        storage_info = storage_class.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)

        return storage_info

    @classmethod
    def get_real_storage_list(cls):
        """
        返回结果表可以支持的所有实际存储列表
        :return: [{"storage_name": "influxdb"}]
        """

        storage_name_list = list(cls.REAL_STORAGE_DICT.keys())
        storage_list = [{"storage_name": storage_name} for storage_name in storage_name_list]

        return storage_list

    @classmethod
    def get_result_table(cls, table_id: str, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        可以使用已有的结果表的命名规范(2_system_cpu_summary)或
        新的命名规范(system_cpu_summary | system.cpu_summary | 2_system.cpu_summary)查询结果表
        :param table_id: 结果表ID
        :param bk_tenant_id: 租户ID
        :return: raise Exception | ResultTable object
        """
        logger.info("get_result_table: try to get rt,bk_tenant_id->[%s],table_id->[%s]", bk_tenant_id, table_id)
        # 0. 尝试直接查询，如果可以命中，则认为符合新的命名规范，直接返回
        query_table_id: str = table_id

        try:
            return cls.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id, is_deleted=False)
        except cls.DoesNotExist:
            # 命中失败，则下面继续
            pass

        bk_biz_id = 0
        result_group = None

        # 1. 判断结果表是否以数字开头及 exporter的数据库
        # 3.2开始使用<database>.<table>
        re_exporter_result = re.match(
            r"((?P<bk_biz_id>\d+)_)?(?P<database>exporter_\w+?)\.(?P<table_id>(\w)+)", table_id
        )
        if not re_exporter_result:
            # 3.2之前兼容<database>_<table>规则：该规则exporter插件名不允许出现关键字_
            re_exporter_result = re.match(
                r"((?P<bk_biz_id>\d+)_)?(?P<database>exporter_\w+?)_(?P<table_id>(\w)+$)", table_id
            )
        re_original_result = re.match(r"((?P<bk_biz_id>\d+)_)?(?P<database>\w+?)(_|\.)(?P<table_id>(\w)+)", table_id)

        # 由于exporter会命中普通的规则，优先匹配exporter的规则
        if re_exporter_result is not None:
            result_group = re_exporter_result.groupdict()

        # exporter规则没有命中，退回到判断是否
        elif re_original_result is not None:
            result_group = re_original_result.groupdict()

        if result_group is not None:
            bk_biz_id = 0 if result_group["bk_biz_id"] is None else result_group["bk_biz_id"]
            table_id = "{}.{}".format(result_group["database"], result_group["table_id"])

        # 2. 使用业务ID及结果表ID来查询获取结果表对象
        try:
            table_id_with_biz = f"{bk_biz_id}_{table_id}"
            return cls.objects.get(
                bk_biz_id=bk_biz_id, table_id=table_id_with_biz, is_deleted=False, bk_tenant_id=bk_tenant_id
            )
        except cls.DoesNotExist:
            logger.info(
                f"table_id->[{table_id_with_biz}] of bk_tenant_id->[{bk_tenant_id}],is search as biz->[{bk_biz_id}] result table and found nothing, "
                "will try to all biz."
            )

        # 如果不能命中，尝试使用退回到全局的结果表查询
        try:
            # 这里是使用旧的结果表判断方式进行判断
            return cls.objects.get(bk_biz_id=0, table_id=table_id, bk_tenant_id=bk_tenant_id, is_deleted=False)
        except cls.DoesNotExist:
            logger.info(
                f"table_id->[{table_id_with_biz}] is search as all biz failed in old style , will try to all biz in new style."
            )
        # 如果使用单指标单表的结果表查询会查询不到真实的结果表
        database_name, _, _ = query_table_id.rpartition(".")
        table_id = f"{database_name}.__default__"
        try:
            return cls.objects.get(table_id=table_id, is_deleted=False, bk_tenant_id=bk_tenant_id)
        except cls.DoesNotExist:
            logger.info(f"table_id->[{table_id}] is search failed, because it not belong split measurement.")

        # 如果找不到，那么就使用新的结果表判断方式进行判断
        re_new_style_result = re.match(
            r"((?P<bk_biz_id>\d+)_)?(?P<database>(\w|_)+?)(\.)(?P<table_id>(\w)+)", query_table_id
        )
        if re_new_style_result is not None:
            result_group = re_new_style_result.groupdict()
            table_id = "{}.{}".format(result_group["database"], result_group["table_id"])

        return cls.objects.get(bk_biz_id=0, table_id=table_id, is_deleted=False, bk_tenant_id=bk_tenant_id)

    @classmethod
    def batch_to_json(cls, result_table_id_list=None, with_option=True, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        批量查询结果表的to_json结果，会加入缺失的几个依赖查询项,禁止跨租户查询
        :param result_table_id_list: ['table_id1', 'table_id2']
        :param with_option: True
        :param bk_tenant_id: 租户ID
        :return:
        """
        # 1. 查询所有依赖的内容
        # rt
        result_table_list = [
            result_table.to_json_self_only()
            for result_table in cls.objects.filter(table_id__in=result_table_id_list, bk_tenant_id=bk_tenant_id)
        ]

        # 字段
        field_dict = {}
        for field in ResultTableField.objects.filter(table_id__in=result_table_id_list, bk_tenant_id=bk_tenant_id):
            try:
                field_dict[field.table_id].append(field.to_json_self_only())
            except KeyError:
                field_dict[field.table_id] = [field.to_json_self_only()]

        # datasource的bk_data_id
        rt_datasource_dict = {
            record.table_id: record.bk_data_id
            for record in DataSourceResultTable.objects.filter(
                table_id__in=result_table_id_list, bk_tenant_id=bk_tenant_id
            )
        }

        # datasource的type_label, source_label
        bk_data_id_list = list(rt_datasource_dict.values())
        datasource_dict = {
            record["bk_data_id"]: record
            for record in DataSource.objects.filter(bk_data_id__in=bk_data_id_list).values(
                "type_label", "source_label", "bk_data_id"
            )
        }  # 这里不需要添加租户ID过滤条件

        field_option_dict = {}
        rt_option_dict = {}
        storage_dict = {}
        if with_option:
            # 字段option
            field_option_dict = ResultTableFieldOption.batch_field_option(
                table_id_list=result_table_id_list, bk_tenant_id=bk_tenant_id
            )
            # RT的option
            rt_option_dict = ResultTableOption.batch_result_table_option(
                table_id_list=result_table_id_list, bk_tenant_id=bk_tenant_id
            )

            # 存储的组合
            storage_dict = {table_id: [] for table_id in result_table_id_list}

            # 禁止跨租户查询
            for storage_name, storage_class in list(cls.REAL_STORAGE_DICT.items()):
                for storage_info in storage_class.objects.filter(
                    table_id__in=result_table_id_list, bk_tenant_id=bk_tenant_id
                ):
                    storage_dict[storage_info.table_id].append(storage_name)

        # 2. 组合
        for result_table_info in result_table_list:
            result_table_name = result_table_info["table_id"]

            # 追加字段名的内容，如果不存在，提供空数组
            result_table_info["field_list"] = field_dict.get(result_table_name, [])
            # 追加DATA_ID信息
            result_table_info["bk_data_id"] = rt_datasource_dict[result_table_name]
            # 追加datasource信息
            result_table_info["type_label"] = datasource_dict[result_table_info["bk_data_id"]]["type_label"]
            result_table_info["source_label"] = datasource_dict[result_table_info["bk_data_id"]]["source_label"]

            if with_option:
                for field_info in result_table_info["field_list"]:
                    field_info["option"] = field_option_dict.get(result_table_name, {}).get(
                        field_info["field_name"], {}
                    )

                # 追加结果表的option
                result_table_info["option"] = rt_option_dict.get(result_table_name, {})
                # 追加存储信息
                result_table_info["storage_list"] = storage_dict[result_table_name]

        return result_table_list

    def create_storage(
        self, storage, is_sync_db, external_storage=None, bk_tenant_id=DEFAULT_TENANT_ID, **storage_config
    ):
        """
        创建结果表的一个实际存储
        :param storage: 存储方案
        :param is_sync_db: 是否需要将配置实际同步到DB
        :param storage_config: 存储方案的配置参数
        :param external_storage: 额外存储方案配置
        :param bk_tenant_id: 租户ID
        :return: True | raise Exception
        """
        # 1. 创建该存储方案对应的实体类并创建存储
        try:
            real_storage = self.REAL_STORAGE_DICT[self.default_storage]
        except KeyError:
            logger.error(f"storage->[{storage}] now is not supported.")
            raise ValueError(_("存储[{}]暂不支持，请确认后重试").format(self.default_storage))

        if self.default_storage == ClusterInfo.TYPE_ES:
            storage_config["enable_create_index"] = False
        real_storage.create_table(
            table_id=self.table_id, bk_tenant_id=bk_tenant_id, is_sync_db=is_sync_db, **storage_config
        )
        logger.info(
            f"result_table->[{self.table_id}] of bk_tenant_id->[{bk_tenant_id}] has create real storage on type->[{storage}]"
        )

        # 3. 判断是否需要存在额外存储的配置支持
        if external_storage is not None:
            for ex_storage_type, ex_storage_config in list(external_storage.items()):
                try:
                    ex_storage = self.REAL_STORAGE_DICT[ex_storage_type]

                except KeyError:
                    logger.error(
                        f"try to set storage->[{ex_storage_type}] for table->[{self.table_id}] of bk_tenant_id->[{bk_tenant_id}] "
                        "but storage is not exists."
                    )
                    raise ValueError(_("存储[{}]暂不支持，请确认后重试").format(ex_storage_type))

                if ex_storage_type == ClusterInfo.TYPE_ES:
                    storage_config["enable_create_index"] = False
                ex_storage.create_table(
                    self.table_id, bk_tenant_id=bk_tenant_id, is_sync_db=is_sync_db, **ex_storage_config
                )
                logger.info(f"result_table->[{self.table_id}] has create real ex_storage on type->[{ex_storage_type}]")

        # 刷新最新版本的ETL配置到consul中
        if is_sync_db:
            try:
                # consul配置如果丢失，则等待cron task刷新
                self.refresh_etl_config()
            except Exception:
                logger.error(
                    f"table_id->[{self.table_id}] of bk_tenant_id->[{bk_tenant_id}] failed to push config to consul for->[{traceback.format_exc()}], wait cron task."
                )

        return True

    def bulk_create_fields(
        self,
        field_data: list[dict[str, Any]],
        is_etl_refresh: bool | None = True,
        is_force_add: bool | None = False,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ) -> True:
        """批量创建新的字段

        # 按照下面步骤执行
        1. 判断该操作时非强制添加，而且结果表是否可以增加字段的模式
        2. 批量添加字段
        3. 遍历所有的实际存储，操作增加字段
        4. 更新ETL配置

        :param field_data: 字段信息，是个列表，列表中为需要插入的每个字段的详细信息
        :param is_etl_refresh: 是否需要更新ETL配置，默认需要更新，但是考虑到部分情景需要等待事务完成，交由上一层把控
        :param is_force_add: 是否需要强制添加字段，用于初始化的时候，其他使用场景不应该使用该字段
        :param bk_tenant_id: 租户ID
        :return: True 或者抛出异常
        """
        # 1. 判断该操作时非强制添加，而且结果表是否可以增加字段的模式
        if not is_force_add and self.schema_type == self.SCHEMA_TYPE_FIXED:
            logger.error("result_table->[%s] schema type is set, no field can be added.", self.table_id)
            raise ValueError(_("结果表[%s]字段不可变更") % self.table_id)

        # 2. 添加字段
        new_field = ResultTableField.bulk_create_fields(
            table_id=self.table_id, field_data=field_data, bk_tenant_id=bk_tenant_id
        )
        # NOTE: 先不处理日志长度，如果后续观察太长，在进行截断处理
        logger.info(
            "new field(name:type)->[%s] for result_table->[%s] now is created.",
            ",".join([f"{field['field_name']}:{field['field_type']}" for field in field_data]),
            self.table_id,
        )

        # 3. 遍历所有的实际存储，操作增加字段
        # NOTE: 下面仅针对计算平台数据库添加字段需要，现阶段没有使用，先注释掉
        # for real_storage in self.real_storage_list:
        #     real_storage.add_field(new_field)
        #     logger.info(
        #         "result_table->[%s] storage->[%s] has added field success.",
        #         self.table_id,
        #         real_storage.STORAGE_TYPE,
        #     )

        # 4. 更新ETL配置
        if is_etl_refresh:
            self.refresh_etl_config()
            logger.info(
                "result_table->[%s]  of bk_tenant_id->[%s] now is finish add field->[%s] and refresh consul config "
                "success.",
                self.table_id,
                bk_tenant_id,
                new_field,
            )

        return True

    def create_field(
        self,
        field_name,
        field_type,
        operator,
        bk_tenant_id=DEFAULT_TENANT_ID,
        is_config_by_user=False,
        default_value=None,
        unit="",
        tag="unknown",
        is_etl_refresh=True,
        is_reserved_check=True,
        is_force_add=False,
        description="",
        alias_name="",
        option=None,
    ):
        """
        该结果表增加一个新的字段
        :param field_name: 字段名
        :param field_type: 字段类型
        :param operator: 操作者
        :param bk_tenant_id: 租户ID
        :param default_value: 默认值，如果为None，则会设置为该类型的空值
        :param unit: 单位
        :param tag: 类型
        :param is_config_by_user: 是否用户配置的字段
        :param is_etl_refresh: 是否需要更新ETL配置，默认需要更新，但是考虑到部分情景需要等待事务完成，交由上一层把控
        :param is_reserved_check: 是否做保留字段检查
        :param is_force_add: 是否需要强制添加字段，用于初始化的时候，其他使用场景不应该使用该字段
        :param description: 字段描述
        :param alias_name: 字段别名
        :param option: 字段选项配置
        :return: True | raise Exception
        """
        logger.info(
            "create_field: try to create field->[%s] for result_table->[%s] of bk_tenant_id->[%s]",
            field_name,
            self.table_id,
            bk_tenant_id,
        )

        # 0. 判断该操作时非强制添加，而且结果表是否可以增加字段的模式
        if not is_force_add and self.schema_type == self.SCHEMA_TYPE_FIXED:
            logger.error(
                "result_table->[{}] of bk_tenant_id->[{}] schema type is set, no field can be added.".format(
                    *self.table_id
                ),
                bk_tenant_id,
            )
            raise ValueError(_("结果表[%s]字段不可变更") % self.table_id)

        # 此处去掉了对字段重名的检查，原因是在ResultTableField的检查会有去重的判断

        with atomic(config.DATABASE_CONNECTION_NAME):
            # 2. 增加新的字段
            new_field = ResultTableField.create_field(
                table_id=self.table_id,
                bk_tenant_id=bk_tenant_id,
                field_name=field_name,
                field_type=field_type,
                is_config_by_user=is_config_by_user,
                default_value=default_value,
                unit=unit,
                tag=tag,
                operator=operator,
                description=description,
                alias_name=alias_name,
                option=option,
                is_reserved_check=is_reserved_check,
            )
            logger.info(
                f"new field->[{field_name}] type->[{field_type}] for result_table->[{self.table_id}] of bk_tenant_id->[{bk_tenant_id}]now is create."
            )

            # 3. 遍历所有的实际存储，操作增加字段操作
            # TODO: 各Storage实体表待补充租户信息
            for real_storage in self.real_storage_list:
                real_storage.add_field(new_field)
                logger.info(
                    f"result_table->[{self.table_id}] storage->[{real_storage.STORAGE_TYPE}] has added field success."
                )

        # 4. 更新ETL配置
        if is_etl_refresh:
            self.refresh_etl_config()
            logger.info(
                f"result_table->[{self.table_id}] of bk_tenant_id->[{bk_tenant_id}] now is finish add field->[{new_field}] and refresh consul config "
                "success."
            )
        return True

    def refresh_etl_config(self):
        """
        更新ETL配置，确保其符合当前数据库配置
        :return: True
        """
        # 刷新RT对应的datasource的ETL配置即可
        bk_data_id = DataSourceResultTable.objects.get(
            table_id=self.table_id, bk_tenant_id=self.bk_tenant_id
        ).bk_data_id

        data_source = DataSource.objects.get(bk_data_id=bk_data_id)
        data_source.refresh_consul_config()
        logger.info("table_id->[%s] of bk_tenant_id->[%s] refresh etl config success", self.table_id, self.bk_tenant_id)

        return True

    def get_storage(self, storage_type):
        storage_class = self.REAL_STORAGE_DICT[storage_type]
        return storage_class.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)

    def get_storage_info(self, storage_type):
        """
        获取结果表一个指定存储的配置信息
        :param storage_type: 存储集群配置
        :return: consul config in dict | raise Exception
        """
        return self.get_storage(storage_type).consul_config

    # TODO: 多租户 待确认
    def raw_delete(self, qs, using=config.DATABASE_CONNECTION_NAME):
        # 考虑公开
        sql.DeleteQuery(qs.model).delete_batch(qs, using)

    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify(
        self,
        operator,
        label=None,
        field_list=None,
        table_name_zh=None,
        default_storage=None,
        include_cmdb_level=False,
        is_time_field_only=False,
        is_reserved_check=True,
        external_storage=None,
        option=None,
        is_enable=None,
        time_option=None,
        data_label=None,
        need_delete_storages=None,
        bk_biz_id_alias=None,
    ):
        """
        修改结果表的配置
        :param operator: 操作者
        :param label: 结果表标签
        :param table_name_zh: 结果表中文名
        :param default_storage: 默认存储方案
        :param field_list: 字段列表
        :param include_cmdb_level:  是否需要创建CMDB层级拆分字段
        :param is_time_field_only: 默认字段是否仅需要时间字段
        :param is_reserved_check: 是否做保留字段检查
        :param external_storage: 额外存储
        :param option: 结果表选项内容
        :param is_enable: 是否启用结果表
        :param time_option: 时间字段配置
        :param data_label: 数据标签
        :param need_delete_storages 需要删除额外存储配置
        :param bk_biz_id_alias: 结果表业务ID别名
        :return: True | raise Exception
        """
        logger.info(
            "modify: try to modify result_table,operator->[%s],table_id->[%s],bk_tenant_id->[%s]",
            operator,
            self.table_id,
            self.bk_tenant_id,
        )

        # 1. 判断是否需要修改中文名
        if table_name_zh is not None:
            self.table_name_zh = table_name_zh

        # 2. 判断是否需要修改默认的存储
        if default_storage is not None:
            # 判断该存储是否真实存在了
            try:
                real_storage_class = self.REAL_STORAGE_DICT[default_storage]

            except KeyError:
                logger.error(
                    "user->[%s] try to set table_id->[%s] default_storage to->[%s] but is not supported by system.",
                    operator,
                    self.table_id,
                    default_storage,
                )
                raise ValueError(_("存储类型[%s]暂不支持，请确认后重试") % default_storage)

            # 如果启用influxdb，当存储类型为influxdb时，校验存储路由存在, 否则，忽略校验
            if (
                settings.ENABLE_INFLUXDB_STORAGE
                and default_storage == ClusterInfo.TYPE_INFLUXDB
                and not real_storage_class.objects.filter(
                    table_id=self.table_id, bk_tenant_id=self.bk_tenant_id
                ).exists()
            ):
                logger.error(
                    "user->[%s] try to set default_storage to->[%s] of bk_tenant_id->[%s] but is not in storage_list.",
                    operator,
                    default_storage,
                    self.bk_tenant_id,
                )
                raise ValueError(_("结果表[{}]不存在存储类型[{}]，请确认").format(self.table_id, default_storage))

            self.default_storage = default_storage

        # 3. 更新结果表字段配置
        if self.schema_type == self.SCHEMA_TYPE_FREE and field_list is not None:
            # 只有是自动字段的结果表，才可以对字段进行修改
            # 需要将字段都先清理后，然后再重新建立该结果表的字段，ETL可以按照新的字段方案进行入库存储
            result_table_field_ids = ResultTableField.objects.filter(
                table_id=self.table_id, is_config_by_user=True, bk_tenant_id=self.bk_tenant_id
            ).values_list("id", flat=True)
            self.raw_delete(result_table_field_ids)

            # option也需要一并的清理
            # 目前rt的option存在清洗和查询两类option，清洗的option需要清理，查询的option需要保留。
            # 目前在option配置的时候并没有标记option的类型，因此只能通过名单的方式进行管理
            # TODO: 后续需要优化option的配置方式，增加option的类型标记
            result_table_field_option_ids = (
                ResultTableFieldOption.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
                .exclude(name__in=ResultTableFieldOption.QUERY_OPTION_NAME_LIST)
                .values_list("id", flat=True)
            )
            self.raw_delete(result_table_field_option_ids)

            logger.info(
                "table_id->[%s] of bk_tenant_id->[%s] all fields and option are deleted for new fields create.",
                self.table_id,
                self.bk_tenant_id,
            )

            # 补充默认字段信息
            ResultTableField.bulk_create_default_fields(
                table_id=self.table_id,
                bk_tenant_id=self.bk_tenant_id,
                include_cmdb_level=include_cmdb_level,
                is_time_field_only=is_time_field_only,
                time_option=time_option,
            )
            logger.info(
                "table_id->[%s] of bk_tenant_id->[%s] default fields is created.", self.table_id, self.bk_tenant_id
            )

            # 批量创建 field 数据，是否需要校验字段由传递参数确认
            for field_info in field_list:
                field_info.update(
                    {
                        "creator": operator,
                        "is_config_by_user": field_info.get("is_config_by_user", True),
                    }
                )
            self.bulk_create_fields(field_list, bk_tenant_id=self.bk_tenant_id, is_etl_refresh=False, is_force_add=True)
            logger.info(
                "table->[%s] of bk_tenant_id->[%s] new field->[%s] is created.",
                self.table_id,
                self.bk_tenant_id,
                ",".join([field["field_name"] for field in field_list]),
            )

            # 判断该结果表是否有依赖的CMDB层级拆分表，这些表都需要依赖一起修改字段
            record_list = CMDBLevelRecord.enable_object.filter(
                source_table_id=self.table_id, bk_tenant_id=self.bk_tenant_id
            )

            # 构造带有CMDB追加信息的字段列表
            change_table_set = set()

            for record in record_list:
                # 需要防止同样的结果表不断的被更新
                if record.target_table_id in change_table_set:
                    logger.info("target result_table->[%s] is already update, nothing will do.", record.target_table_id)
                    continue

                target_table = ResultTable.objects.get(table_id=record.target_table_id, bk_tenant_id=self.bk_tenant_id)
                # 由于此处都是处理CMDB拆分表，所以都需要增加上cmdb拆分字段
                target_table.modify(operator=operator, field_list=field_list, include_cmdb_level=True)

                change_table_set.add(target_table.table_id)
                logger.info(
                    "source result_table->[%s] has relay cmdb_level target result_table->[%s] now has modify field.",
                    self.table_id,
                    record.target_table_id,
                )

        # 4. 判断标签是否需要修改
        if label is not None:
            if not Label.exists_label(label_id=label, label_type=Label.LABEL_TYPE_RESULT_TABLE):
                logger.error(
                    "user->[%s] try to update rt->[%s] of bk_tenant_id->[%s] to label->[%s] but is not exists, "
                    "nothing will do.",
                    operator,
                    self.table_id,
                    self.bk_tenant_id,
                    label,
                )
                raise ValueError(_("标签[{}]不存在，请确认后重试").format(label))
            self.label = label

        # 5. 判断是否有额外的存储需要创建
        # 由于空字典不可以作为默认值，因此此处需要做一个兼容处理
        external_storage = {} if external_storage is None else external_storage
        for ex_storage_type, ex_storage_config in list(external_storage.items()):
            try:
                ex_storage = self.REAL_STORAGE_DICT[ex_storage_type]

            except KeyError:
                logger.error(
                    "try to set storage->[%s] for table->[%s] of bk_tenant_id->[%s] but storage is not exists.",
                    ex_storage_type,
                    self.table_id,
                    self.bk_tenant_id,
                )
                raise ValueError(_("存储[{}]暂不支持，请确认后重试").format(ex_storage_type))

            # 需要先判断该额外存储是否已经存在了
            storage_query = ex_storage.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
            if storage_query.exists():
                logger.info(
                    "table->[%s] of bk_tenant_id->[%s] is already has storage->[%s] config, nothing will added.",
                    self.table_id,
                    self.bk_tenant_id,
                    ex_storage_type,
                )
                storage = storage_query.get()
                storage.update_storage(**ex_storage_config)
                logger.info("table->[%s] upgrade storage->[%s] config success.", self.table_id, ex_storage_type)
                continue

            ex_storage.create_table(self.table_id, bk_tenant_id=self.bk_tenant_id, is_sync_db=True, **ex_storage_config)
            logger.info(
                "result_table->[%s] of bk_tenant_id->[%s] has create real ex_storage on type->[%s]",
                self.table_id,
                self.bk_tenant_id,
                ex_storage_type,
            )

            # 删除额外存储配置
            need_delete_storages = need_delete_storages or {}
            for storage_type, delete_storage in need_delete_storages.items():
                if storage_type not in self.REAL_STORAGE_DICT:
                    logger.info(
                        "try to delete storage->[%s] for table->[%s] but storage is not exists.",
                        storage_type,
                        self.table_id,
                    )
                    continue
                ex_storage = self.REAL_STORAGE_DICT[storage_type]
                ex_storage.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).delete()
                logger.info("table->[%s] delete storage->[%s] config success.", self.table_id, storage_type)

        # 更新结果表option配置
        if option is not None:
            # 目前rt的option存在清洗和查询两类option，清洗的option需要清理，查询的option需要保留。
            # 目前在option配置的时候并没有标记option的类型，因此只能通过名单的方式进行管理
            # TODO: 后续需要优化option的配置方式，增加option的类型标记
            result_table_option_ids = (
                ResultTableOption.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
                .exclude(name__in=list(set(ResultTableFieldOption.QUERY_OPTION_NAME_LIST) - set(option.keys())))
                .values_list("id", flat=True)
            )
            self.raw_delete(result_table_option_ids)

            logger.info(
                "table_id->[%s] of bk_tenant_id->[%s] has delete all the result table options.",
                self.table_id,
                self.bk_tenant_id,
            )
            # 批量写入
            ResultTableOption.bulk_create_options(
                table_id=self.table_id, option_data=option, creator=operator, bk_tenant_id=self.bk_tenant_id
            )

        # 是否需要修改结果表是否启用
        if is_enable is not None:
            self.is_enable = is_enable
            self.save()  # 这里需要保存下，下面的es索引创建逻辑会依赖is_enable的判断
            logger.info(
                f"table_id->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] is change to is_enable->[{self.is_enable}]"
            )

            # 如果启用结果表，需要创建结果表的实际存储依赖
            if is_enable:
                # 需要判断存储方式是否有明确的结果表创建
                # 目前只需要判断ES，influxdb，kafka和redis会有自动创建能力
                es_query = ESStorage.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
                if es_query.exists():
                    es_storage = es_query.get()
                    if not es_storage.index_exist():
                        #   如果该table_id的index在es中不存在，说明要走初始化流程
                        logger.info(
                            "table_id->[%s] of bk_tenant_id->[%s] found no index in es, will create new one",
                            es_storage.table_id,
                            self.bk_tenant_id,
                        )
                        es_storage.create_index_and_aliases(es_storage.slice_gap)
                    else:
                        # 否则走更新流程
                        es_storage.update_index_and_aliases(ahead_time=es_storage.slice_gap)

                    logger.info(
                        f"table_id->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] is change to is_enable {self.is_enable} and es index is created"
                    )

        if bk_biz_id_alias is not None:
            logger.info(
                "modify_result_table: table_id->[%s] got new_bk_biz_id_alias->[%s]", self.table_id, bk_biz_id_alias
            )
            self.bk_biz_id_alias = bk_biz_id_alias
            SpaceTypeToResultTableFilterAlias.objects.update_or_create(
                table_id=self.table_id, defaults={"space_type": SpaceTypes.BKCC.value, "filter_alias": bk_biz_id_alias}
            )

        # 是否需要修改数据标签
        if data_label is not None:
            self.data_label = data_label

        self.last_modify_user = operator
        self.save()

        # 异步执行时，需要在commit之后，以保证所有操作都提交
        # TODO：多租户改造--路由推送是否需要携带租户信息
        try:
            from metadata.models.space.utils import get_space_by_table_id
            from metadata.task.tasks import push_and_publish_space_router

            space_info = get_space_by_table_id(self.table_id, bk_tenant_id=self.bk_tenant_id)
            space_type, space_id = space_info.get("space_type_id"), space_info.get("space_id")
            if self.default_storage == ClusterInfo.TYPE_INFLUXDB:
                if space_id and space_type:
                    push_and_publish_space_router(space_type, space_id, table_id_list=[self.table_id])
                else:
                    on_commit(
                        lambda: push_and_publish_space_router.delay(space_type, space_id, table_id_list=[self.table_id])
                    )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("push and publish redis error, table_id: %s, %s", self.table_id, e)

        # 刷新清洗配置
        self.refresh_etl_config()
        logger.info("table_id->[%s] of bk_tenant_id->[%s] updated success.", self.table_id, self.bk_tenant_id)

    # TODO: 多租户 计算平台关联接口，暂未改造
    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
    def notify_bkdata_log_data_id_changed(self, data_id):
        """
        通知计算平台，ES相关配置变更
        @param data_id: 数据源ID
        """
        try:
            api.bkdata.notify_log_data_id_changed(data_id=data_id)
            logger.info(
                f"notify_log_data_id_changed table_id->{self.table_id},data_id ->{data_id},notify es config changed success."
            )
            return True  # 成功时返回
        except Exception as e:
            logger.error(
                "notify_log_data_id_changed table_id->[%s],data_id ->[%s],notify es config changed error->[%s]",
                self.table_id,
                data_id,
                e,
            )
            raise e

    @atomic(config.DATABASE_CONNECTION_NAME)
    def upgrade_result_table(self, operator):
        """
        将单业务结果表升级为全业务结果表
        :param operator: 操作者
        :return:
        """
        logger.info(
            "upgrade_result_table: table_id->[%s],bk_tenant_id->[%s],operator->[%s]",
            self.table_id,
            self.bk_tenant_id,
            operator,
            operator,
        )

        # 1. 判断结果表是否已经是全业务
        if self.bk_biz_id == 0 or self.is_deleted:
            logger.error(
                f"user->[{operator}] result_table->[{self.table_id}] is already deleted or all business table, nothing will do."
            )
            raise ValueError(_("结果表不可操作，请确认后重试"))

        # 2. 标记自身已经不可用
        self.is_deleted = True
        self.bk_biz_id = 0
        self.last_modify_user = operator
        self.last_modify_time = datetime.datetime.now()
        # 必须在此时就save，否则后面改了table_id(主键)就不能修改已有数据了
        self.save()

        logger.info(f"result_table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] now is marked deleted.")

        new_table_id = re.match(r"\d+_(?P<table_id>(\w|_|\.)+)", self.table_id).group("table_id")

        # 3. 结果表已有信息迁移
        # 3.1 字段迁移
        ResultTableField.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).update(
            table_id=new_table_id
        )
        logger.info(
            f"result_table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] all fields is set to result_table->[{new_table_id}]"
        )

        # 3.2 新建存储记录
        for storage_str in list(self.REAL_STORAGE_DICT.keys()):
            storage_config = self.REAL_STORAGE_DICT[storage_str]

            try:
                storage = storage_config.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)

            except storage_config.DoesNotExist:
                continue

            new_storage = copy.deepcopy(storage)
            storage.delete()
            new_storage.table_id = new_table_id
            new_storage.bk_tenant_id = self.bk_tenant_id
            new_storage.save()
            logger.info(
                f"result_table->[{self.table_id}] storage->[{storage_str}] now is give to new_result_table->[{new_table_id}]"
            )

        # 3.3 DataID与结果表关系迁移
        DataSourceResultTable.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).update(
            table_id=new_table_id
        )
        logger.info(
            f"result_table->[{self.table_id}] all data_source config to give to new_table_table->[{new_table_id}]"
        )

        # 3.4 复制自身数据到新结果表
        self.table_id = new_table_id
        self.save()
        logger.info(f"new_result_table->[{new_table_id}] now is update success.")

        return True

    @atomic(config.DATABASE_CONNECTION_NAME)
    def set_metric_split(self, cmdb_level, operator):
        """
        设置一个结果表的CMDB层级拆分任务
        :param cmdb_level: cmdb层级名
        :param operator: 操作者
        :return: CMDBLevelRecord object
        """
        # 0. 判断是否小于10000的原生数据源配置，如果是，不可以进行拆分配置
        try:
            data_id = DataSourceResultTable.objects.get(
                table_id=self.table_id, bk_tenant_id=self.bk_tenant_id
            ).bk_data_id

        except DataSourceResultTable.DoesNotExist:
            logger.error(
                f"failed to get table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] datasource as it is not exists, maybe something go "
                "wrong?"
            )
            raise ValueError(_("结果表[{}]不存在关联数据源").format(self.table_id))

        # 如果不允许全局创建CMDB_LEVEL，而且data_id是小于10000的，禁止创建
        if not settings.IS_ALLOW_ALL_CMDB_LEVEL and data_id < 10000:
            logger.error(f"cannot split data_id->[{data_id}] table_id->[{self.table_id}] as it is under 10000.")
            raise ValueError(_("公共数据源不允许配置拆分任务"))

        # 1. 判断是否存在已有该拆分任务
        if CMDBLevelRecord.is_level_exists(
            source_table_id=self.table_id, cmdb_level=cmdb_level, bk_tenant_id=self.bk_tenant_id
        ):
            # 如果已经存在类似的拆分任务，直接退出
            logger.info(
                f"table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] for cmdb_level->[{cmdb_level}] already exists, "
                "no new table will create."
            )
            return CMDBLevelRecord.objects.get(
                source_table_id=self.table_id, cmdb_level=cmdb_level, bk_tenant_id=self.bk_tenant_id
            )

        # 如果结果表已经是一个拆分结果的内容，不必再进行拆分
        if CMDBLevelRecord.objects.filter(target_table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).exists():
            logger.error(
                f"table_id->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] is already cmdb_level targe table, nothing will be split any "
                "more."
            )
            raise ValueError(_("不可对拆分结果表再次拆分"))

        # 2. 找到这个结果表输出的结果表
        # 如果已经存在的，可以直接复用；否则需要创建一个新的
        try:
            data_source = CMDBLevelRecord.get_table_data_source(
                source_table_id=self.table_id, bk_tenant_id=self.bk_tenant_id
            )

        except CMDBLevelRecord.DoesNotExist:
            # 如果未能找到已有的记录，需要创建一个新的数据源
            data_source = DataSource.create_data_source(
                data_name=config.RT_CMDB_LEVEL_DATA_SOURCE_NAME.format(self.table_id),
                bk_tenant_id=self.bk_tenant_id,
                # 由于重复流转之后的数据，都是标准格式数据，因此此处写死是bk_standard即可
                etl_config="bk_standard",
                operator=operator,
                is_refresh_config=False,
                source_label=self.data_source.source_label,
                type_label=self.data_source.type_label,
            )
            logger.info(
                f"new data_id->[{data_source.bk_data_id}] is create for table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] for cmdb_level."
            )

            # 判断RT是否已经存在Kafka输出，如果有，则将上述的data_source指向这个kafka
            if KafkaStorage.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).exists():
                storage = KafkaStorage.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).first()
                logger.info(
                    f"result_table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] already has kafka storage will set topic->[{storage.topic}] "
                    f"partition->[{storage.partition}]"
                )

            # 否则创建一个新的kafka结果表
            else:
                storage = KafkaStorage.create_table(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
                logger.info(f"result_table->[{self.table_id}] create new kafka storage for cmdb_level.")

            data_source.mq_config.topic = storage.topic
            data_source.mq_config.partition = storage.partition
            data_source.mq_config.save()

        # 4. data_id增加一个新的结果表内容
        record = CMDBLevelRecord.create_record(
            source_table_id=self.table_id,
            bk_data_id=data_source.bk_data_id,
            cmdb_level=cmdb_level,
            operator=operator,
            bk_tenant_id=self.bk_tenant_id,
        )
        logger.info(
            f"table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] cmdb_level->[{cmdb_level}] create/reuse table->[{record.target_table_id}]"
        )

        return record

    @atomic(config.DATABASE_CONNECTION_NAME)
    def clean_metric_split(self, cmdb_level, operator):
        """
        清理一个CMDB_LEVEL拆分配置记录
        :param cmdb_level: cmdb层级记录名
        :param operator: 操作者
        :return: True | False
        """
        # 1. 判断是否存在该metric的拆分记录
        if not CMDBLevelRecord.objects.filter(
            source_table_id=self.table_id, cmdb_level=cmdb_level, bk_tenant_id=self.bk_tenant_id
        ).exists():
            logger.error(
                f"try to delete cmdb_level->[{cmdb_level}] for table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] but is not exist."
            )
            raise ValueError(_("结果表不存在该字段拆分记录"))

        # 2. 去掉cmdb_level信息
        record = CMDBLevelRecord.objects.get(
            source_table_id=self.table_id, cmdb_level=cmdb_level, bk_tenant_id=self.bk_tenant_id
        )
        record.delete()
        logger.info(
            f"cmdb level->[{cmdb_level}] for table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}]now is deleted."
        )

        # 3. 重新覆盖option的记录
        # 注意，这里清理后，并没有进一步的清理数据源或者结果表
        # 原因是，Transfer如果发现这个cmdb_level为空后，会不再对该结果表入库，没有存储消耗问题
        ResultTableOption.sync_cmdb_level_option(
            table_id=record.target_table_id, operator=operator, bk_tenant_id=self.bk_tenant_id
        )
        logger.info(
            f"update table_id->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] result_table cmdb_level option success."
        )

        return True

    def to_json(self):
        query_alias_settings = None
        if self.default_storage == ClusterInfo.TYPE_ES:
            query_alias_settings = ESFieldQueryAliasOption.generate_query_alias_settings(self.table_id)
        data = {
            "table_id": self.table_id,
            "bk_tenant_id": self.bk_tenant_id,
            "table_name_zh": _(self.table_name_zh),
            "is_custom_table": self.is_custom_table,
            "scheme_type": self.schema_type,
            "default_storage": self.default_storage,
            "storage_list": self.storage_list,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
            "field_list": [
                field_info.to_json() for field_info in ResultTableField.objects.filter(table_id=self.table_id)
            ],
            "bk_biz_id": self.bk_biz_id,
            "option": ResultTableOption.get_option(self.table_id),
            "label": self.label,
            "bk_data_id": self.data_source.bk_data_id if self.default_storage != ClusterInfo.TYPE_BKDATA else None,
            "is_enable": self.is_enable,
            "data_label": self.data_label,
        }

        if query_alias_settings:
            data["query_alias_settings"] = query_alias_settings
        return data

    def to_json_self_only(self):
        """
        仅返回自身相关的信息json格式，其他的内容需要调用方自行追加，目前已知需要用户自定义添加的内容
        1. field_list, 字段内容
        2. option, 结果表选线内容
        3. storage_list, 存储列表
        4. bk_data_id, 数据源ID
        :return:
        """

        return {
            "table_id": self.table_id,
            "bk_tenant_id": self.bk_tenant_id,
            "table_name_zh": self.table_name_zh,
            "is_custom_table": self.is_custom_table,
            "scheme_type": self.schema_type,
            "default_storage": self.default_storage,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
            "bk_biz_id": self.bk_biz_id,
            "label": self.label,
            "is_enable": self.is_enable,
            "data_label": self.data_label,
        }

    def get_tag_values(self, tag_name):
        for real_storage in self.real_storage_list:
            if hasattr(real_storage, "get_tag_values"):
                return real_storage.get_tag_values(
                    tag_name
                )  # 这里无需补充租户ID作为查询条件,因为real_storage已经进行了过滤

        raise NotImplementedError("no storage support get_tag_values")

    @classmethod
    def get_table_id_and_data_id(cls, bk_biz_id: int, bk_tenant_id=DEFAULT_TENANT_ID) -> list[dict]:
        """
        获取结果表和数据源 ID,禁止跨租户获取
        """
        table_id_list = cls.objects.filter(bk_biz_id=bk_biz_id, bk_tenant_id=bk_tenant_id).values_list(
            "table_id", flat=True
        )
        # 过滤 table_id 对应的数据源 ID
        return list(
            DataSourceResultTable.objects.filter(table_id__in=table_id_list, bk_tenant_id=bk_tenant_id).values(
                "table_id", "bk_data_id"
            )
        )


class ResultTableField(models.Model):
    """逻辑结果表字段"""

    FIELD_TYPE_INT = "int"
    FIELD_TYPE_LONG = "long"
    FIELD_TYPE_FLOAT = "float"
    FIELD_TYPE_STRING = "string"
    FIELD_TYPE_BOOLEAN = "boolean"
    FIELD_TYPE_OBJECT = "object"
    FIELD_TYPE_NESTED = "nested"
    FIELD_TYPE_TIMESTAMP = "timestamp"

    FIELD_TYPE_CHOICES = (
        (FIELD_TYPE_INT, _("整型")),
        (FIELD_TYPE_FLOAT, _("浮点型")),
        (FIELD_TYPE_STRING, _("字符型")),
        (FIELD_TYPE_BOOLEAN, _("布尔型")),
        (FIELD_TYPE_TIMESTAMP, _("时间字段")),
    )

    # 对于TSDB，字段类型表示
    # 指标字段
    FIELD_TAG_METRIC = "metric"
    # 维度字段
    FIELD_TAG_DIMENSION = "dimension"
    # 时间字段
    FIELD_TAG_TIMESTAMP = "timestamp"
    # 标签字段（对于数据库而言，标签实际为维度字段）
    FIELD_TAG_GROUP = "group"

    TAG_CHOICES = (
        ("unknown", _("未知类型字段")),
        (FIELD_TAG_DIMENSION, _("维度字段")),
        (FIELD_TAG_METRIC, _("指标字段")),
        (FIELD_TAG_TIMESTAMP, _("时间戳字段")),
        (FIELD_TAG_GROUP, _("标签字段")),
        ("const", _("常量")),
    )

    # GSE agent ID
    FIELD_DEF_BK_AGENT_ID = {
        "field_name": "bk_agent_id",
        "field_type": FIELD_TYPE_STRING,
        "unit": "",
        "is_config_by_user": True,
        "default_value": "",
        "operator": "system",
        "tag": FIELD_TAG_DIMENSION,
        "description": "Agent ID",
        "alias_name": "",
    }
    # CMDB host ID
    FIELD_DEF_BK_HOST_ID = {
        "field_name": "bk_host_id",
        "field_type": FIELD_TYPE_STRING,
        "unit": "",
        "is_config_by_user": True,
        "default_value": "",
        "operator": "system",
        "tag": FIELD_TAG_DIMENSION,
        "description": "采集主机ID",
        "alias_name": "",
    }

    # CMDB host ID
    FIELD_DEF_BK_TARGET_HOST_ID = {
        "field_name": "bk_target_host_id",
        "field_type": FIELD_TYPE_STRING,
        "unit": "",
        "is_config_by_user": True,
        "default_value": "",
        "operator": "system",
        "tag": FIELD_TAG_DIMENSION,
        "description": "目标主机ID",
        "alias_name": "",
    }

    table_id = models.CharField("结果表名", max_length=128)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    field_name = models.CharField("字段名", max_length=255, db_collation="utf8_bin")
    field_type = models.CharField("字段类型", max_length=32, choices=FIELD_TYPE_CHOICES)
    description = models.TextField("字段描述", blank=True, default="")
    # 单位存在默认值，默认为空
    unit = models.CharField("字段单位", max_length=32, default="")
    tag = models.CharField("字段标签", max_length=16, choices=TAG_CHOICES)
    # 存在某些字段，是有清洗模块发现的，
    # 但该部分的字段只能缓存与元数据数据库中，不能直接生效到结果数据库中
    is_config_by_user = models.BooleanField("是否用户确认字段")
    default_value = models.CharField("字段默认值", max_length=128, default=None, null=True)
    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    # 字段别名，默认为空，以支持部分keyword
    alias_name = models.CharField("字段映射前（上传时）名", default="", max_length=64)
    is_disabled = models.BooleanField("是否禁用", default=False)

    class Meta:
        # 一个结果表的字段名不可能重复
        unique_together = ("table_id", "field_name", "bk_tenant_id")
        verbose_name = "结果表字段"
        verbose_name_plural = "结果表字段表"

    def __unicode__(self):
        return f"table->[{self.table_id}]: field->[{self.field_name}]"

    @property
    def is_dimension(self):
        return self.tag == "dimension"

    @property
    def is_metric(self):
        return self.tag == "metric"

    @classmethod
    def bulk_create_default_fields(
        cls,
        table_id: str,
        include_cmdb_level: bool | None = False,
        is_time_field_only: bool | None = False,
        time_alias_name: str | None = None,
        time_option: str | None = None,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ) -> None:
        """批量创建默认字段， 包含 time，bk_biz_id，bk_supplier_id，bk_cloud_id，ip，bk_cmdb_level

        :param table_id: 结果表 ID
        :param include_cmdb_level: 是否包含CMDB拆分字段，默认为 False
        :param is_time_field_only: 是否仅包含创建时间字段，兼容ES的创建需求，默认为 False
        :param time_alias_name: 时间字段的别名配置
        :param time_option: 时间字段选项
        :param bk_tenant_id: 租户ID
        """
        # NOTE: 公共字段直接列举到对应的字段中，减少计算
        # 组装要创建的默认字段数据
        # 上报时间
        logger.info(
            "bulk_create_default_fields: table_id->[%s], bk_tenant_id->[%s] try to create default fields",
            table_id,
            bk_tenant_id,
        )

        time_field_data = {
            "field_name": "time",
            "field_type": cls.FIELD_TYPE_TIMESTAMP,
            "unit": "",
            "is_config_by_user": True,
            "default_value": "",
            "operator": "system",
            "description": _("数据上报时间"),
            "tag": cls.FIELD_TAG_TIMESTAMP,
            "alias_name": "" if time_alias_name is None else time_alias_name,
            "option": time_option,
        }
        # 当限制仅包含时间字段时，创建时间字段，然后返回
        if is_time_field_only:
            cls.create_field(table_id, bk_tenant_id=bk_tenant_id, is_reserved_check=False, **time_field_data)
            logger.info("table->[%s] is need time only, no more fields will create.", table_id)
            return
        # 业务 ID
        bk_biz_id_field_data = {
            "field_name": "bk_biz_id",
            "field_type": cls.FIELD_TYPE_INT,
            "unit": "",
            "is_config_by_user": True,
            "default_value": "-1",
            "operator": "system",
            "tag": cls.FIELD_TAG_DIMENSION,
            "description": _("业务ID"),
            "alias_name": "",
        }
        # 开发商 ID
        bk_supplier_id_field_data = {
            "field_name": "bk_supplier_id",
            "field_type": cls.FIELD_TYPE_INT,
            "unit": "",
            "is_config_by_user": True,
            "default_value": "-1",
            "operator": "system",
            "tag": cls.FIELD_TAG_DIMENSION,
            "description": _("开发商ID"),
            "alias_name": "",
        }
        # 云区域 ID
        bk_cloud_id_field_data = {
            "field_name": "bk_cloud_id",
            "field_type": cls.FIELD_TYPE_INT,
            "unit": "",
            "is_config_by_user": True,
            "default_value": "-1",
            "operator": "system",
            "tag": cls.FIELD_TAG_DIMENSION,
            "description": _("采集器云区域ID"),
            "alias_name": "",
        }
        # IP 地址
        ip_field_data = {
            "field_name": "ip",
            "field_type": cls.FIELD_TYPE_STRING,
            "unit": "",
            "is_config_by_user": True,
            "default_value": "",
            "operator": "system",
            "tag": cls.FIELD_TAG_DIMENSION,
            "description": _("采集器IP"),
            "alias_name": "",
        }
        # CMDB 层级记录信息
        bk_cmdb_level_field_data = {
            "field_name": "bk_cmdb_level",
            "field_type": cls.FIELD_TYPE_STRING,
            "unit": "",
            "is_config_by_user": True,
            "default_value": "",
            "operator": "system",
            "tag": cls.FIELD_TAG_DIMENSION,
            "description": _("CMDB层级信息"),
            "alias_name": "",
        }
        # 批量添加字段
        cls.bulk_create_fields(
            table_id=table_id,
            field_data=[
                time_field_data,
                bk_biz_id_field_data,
                bk_supplier_id_field_data,
                bk_cloud_id_field_data,
                ip_field_data,
                bk_cmdb_level_field_data,
                cls.FIELD_DEF_BK_AGENT_ID,
                cls.FIELD_DEF_BK_HOST_ID,
                cls.FIELD_DEF_BK_TARGET_HOST_ID,
            ],
            bk_tenant_id=bk_tenant_id,
        )

        # 对于CMDB层级拆分结果表，需要追加两个相关的字段
        if include_cmdb_level:
            cls.make_cmdb_default_fields(table_id=table_id, bk_tenant_id=bk_tenant_id)

        # 当前cmdb_level默认都不需要写入influxdb, 防止维度增长问题
        ResultTableFieldOption.create_option(
            table_id=table_id,
            field_name="bk_cmdb_level",
            name=ResultTableFieldOption.OPTION_INFLUXDB_DISABLED,
            value=True,
            creator="system",
            bk_tenant_id=bk_tenant_id,
        )

        logger.info("all default field is created for table->[%s] of bk_tenant_id->[%s].", table_id, bk_tenant_id)

    @classmethod
    def make_default_fields(
        cls,
        table_id,
        bk_tenant_id=DEFAULT_TENANT_ID,
        include_cmdb_level=False,
        is_time_field_only=False,
        time_alias_name=None,
        time_option=None,
    ):
        """
        创建默认字段信息
        :param table_id: 结果表ID
        :param bk_tenant_id: 租户ID
        :param include_cmdb_level: 是否包含CMDB拆分字段
        :param is_time_field_only: 是否仅包含创建时间字段，兼容ES的创建需求
        :param time_alias_name: 时间字段的别名配置
        :param time_option: 时间字段选项
        :return: True | False
        """
        # 上报时间
        cls.create_field(
            table_id=table_id,
            field_name="time",
            bk_tenant_id=bk_tenant_id,
            field_type=cls.FIELD_TYPE_TIMESTAMP,
            is_config_by_user=True,
            default_value="",
            operator="system",
            description=_("数据上报时间"),
            tag=cls.FIELD_TAG_TIMESTAMP,
            is_reserved_check=False,
            alias_name="" if time_alias_name is None else time_alias_name,
            option=time_option,
        )
        if is_time_field_only:
            logger.info(f"table->[{table_id}] is need time only, no more fields will create.")
            return

        # 业务ID
        cls.create_field(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="bk_biz_id",
            field_type=cls.FIELD_TYPE_INT,
            is_config_by_user=True,
            default_value="-1",
            operator="system",
            tag=cls.FIELD_TAG_DIMENSION,
            description=_("业务ID"),
            is_reserved_check=False,
        )

        # 开发商ID
        cls.create_field(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="bk_supplier_id",
            field_type=cls.FIELD_TYPE_INT,
            is_config_by_user=True,
            default_value="-1",
            operator="system",
            tag=cls.FIELD_TAG_DIMENSION,
            description=_("开发商ID"),
            is_reserved_check=False,
        )

        # 云区域ID
        cls.create_field(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="bk_cloud_id",
            field_type=cls.FIELD_TYPE_INT,
            is_config_by_user=True,
            default_value="-1",
            operator="system",
            tag=cls.FIELD_TAG_DIMENSION,
            description=_("采集器云区域ID"),
            is_reserved_check=False,
        )

        # IP地址
        cls.create_field(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="ip",
            field_type=cls.FIELD_TYPE_STRING,
            is_config_by_user=True,
            default_value="",
            operator="system",
            tag=cls.FIELD_TAG_DIMENSION,
            description=_("采集器IP"),
            is_reserved_check=False,
        )

        # CMDB层级记录信息
        cls.create_field(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="bk_cmdb_level",
            field_type=cls.FIELD_TYPE_STRING,
            is_config_by_user=True,
            default_value="",
            operator="system",
            tag=cls.FIELD_TAG_DIMENSION,
            description=_("CMDB层级信息"),
            is_reserved_check=False,
        )

        # 对于CMDB层级拆分结果表，需要追加两个相关的字段
        if include_cmdb_level:
            cls.make_cmdb_default_fields(table_id=table_id, bk_tenant_id=bk_tenant_id)

        # 当前cmdb_level默认都不需要写入influxdb, 防止维度增长问题
        ResultTableFieldOption.create_option(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="bk_cmdb_level",
            name=ResultTableFieldOption.OPTION_INFLUXDB_DISABLED,
            value=True,
            creator="system",
        )

        logger.info(f"all default field is created for table->[{table_id}].")

    @classmethod
    def make_cmdb_default_fields(cls, table_id, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        增加CMDB层级拆分的字段内容
        :param table_id: 结果表ID
        :param bk_tenant_id: 租户ID
        :return: True | raise Exception
        """
        logger.info(
            "make_cmdb_default_fields: try to add default cmdb_fields for table_id->[%s] of bk_tenant_id->[%s]",
            table_id,
            bk_tenant_id,
        )
        cls.create_field(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="bk_obj_id",
            field_type=cls.FIELD_TYPE_STRING,
            is_config_by_user=True,
            default_value="",
            operator="system",
            tag=cls.FIELD_TAG_DIMENSION,
            description=_("CMDB层级名"),
            is_reserved_check=False,
        )

        cls.create_field(
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            field_name="bk_inst_id",
            field_type=cls.FIELD_TYPE_STRING,
            is_config_by_user=True,
            default_value="",
            operator="system",
            tag=cls.FIELD_TAG_DIMENSION,
            description=_("CMDB层级ID"),
            is_reserved_check=False,
        )
        logger.info(f"table->[{table_id}] of bk_tenant_id->[{bk_tenant_id}] now has created default cmdb field.")

    def _check_reserved_fields(self, uppercase_field_names: list[str]):
        """校验字段是否为保留字段"""
        # TODO: 确认是否可以 `RT_RESERVED_WORD_EXACT` 小写处理，因为在配置中有小写字段
        same_field_names = set(uppercase_field_names) & set(config.RT_RESERVED_WORD_EXACT)
        if not same_field_names:
            return
        # 记录日志并抛出异常
        # 以半角逗号拼接
        joined_names = ",".join([field.lower() for field in same_field_names])
        logger.error("try to create filed [%s] which are reserved fields, nothing will added.", joined_names)
        raise ValueError(_("字段[{}]为保留字段，不可创建").format(joined_names))

    def _check_existed_fields(self, table_id: str, field_names: list[str], bk_tenant_id=DEFAULT_TENANT_ID):
        """校验字段是否已经创建"""

        existed_field_names = ResultTableField.objects.filter(
            table_id=table_id, field_name__in=field_names, bk_tenant_id=bk_tenant_id
        ).values_list("field_name", flat=True)
        if not existed_field_names:
            return

        # 记录日志并抛出异常
        joined_names = ",".join(existed_field_names)
        logger.error("field->[%s] is exists under table->[%s], nothing will be added.", joined_names, table_id)
        raise ValueError(_("字段[{}]已在表[{}]中存在，请确认").format(joined_names, table_id))

    def _compose_data(
        self, table_id: str, field_data: list[dict[str, Any]], bk_tenant_id: str | None = DEFAULT_TENANT_ID
    ) -> tuple[list, list, list]:
        """组装数据"""
        logger.info(
            "compose data for table->[%s],field_data->[%s],bk_tenant_id->[%s", table_id, field_data, bk_tenant_id
        )
        fields, field_names, option_data = [], [], []
        for field in field_data:
            # 不影响传递的参数
            _field = copy.deepcopy(field)
            _field.pop("is_reserved_check", None)
            # 添加结果表 ID
            _field["table_id"] = table_id
            _field["bk_tenant_id"] = bk_tenant_id
            _field["creator"] = _field.pop("operator", "")
            field_names.append(_field["field_name"])
            # 处理 option
            option = _field.pop("option", None)
            # 组装新的 field 参数
            fields.append(_field)
            if not option:
                continue
            # 组装 option 数据
            option_data.extend(
                [
                    {
                        "table_id": _field["table_id"],
                        "field_name": _field["field_name"],
                        "name": key,
                        "value": val,
                        "creator": _field["creator"],
                    }
                    for key, val in option.items()
                ]
            )

        return fields, field_names, option_data

    @classmethod
    def bulk_create_fields(
        cls, table_id: str, field_data: list[dict[str, Any]], bk_tenant_id=DEFAULT_TENANT_ID
    ) -> bool:
        """批量创建 fields

        # 分为下面几步处理
        1. 校验字段是否为预留字段
        2. 校验字段是否已经创建
        3. 创建字段信息
        4. 创建 option

        :param table_id: 结果表 ID
        :param field_data: field 信息，可以考虑增加一个 `dataclass` 用于传递参数
        :param bk_tenant_id: 租户ID
        :return: 返回 True 或者抛出异常
        """
        # 获取需要校验的字段，然后检查是否已经被占用
        logger.info(
            "bulk_create_fields: table_id->[%s],bk_tenant_id->[%s,field_data->[%s] start to create fields",
            table_id,
            bk_tenant_id,
            field_data,
        )

        uppercase_field_names = [field["field_name"].upper() for field in field_data if field.get("is_reserved_check")]
        if uppercase_field_names:
            cls()._check_reserved_fields(uppercase_field_names)

        # 组装必要数据，用于后续的处理
        fields, field_names, option_data = cls()._compose_data(table_id, field_data)

        # 校验字段是否已经创建
        cls()._check_existed_fields(table_id, field_names)

        # 写入数据
        cls.objects.bulk_create([cls(**field) for field in fields])

        logger.info(
            "new field ->[%s] is create for table->[%s],bk_tenant_id->[%s]",
            ",".join(field_names),
            table_id,
            bk_tenant_id,
        )

        # 如果 option 数据存在，则批量写入
        ResultTableFieldOption.bulk_create_options(
            table_id=table_id, option_data=option_data, bk_tenant_id=bk_tenant_id
        )

    @classmethod
    def create_field(
        cls,
        table_id,
        field_name,
        field_type,
        is_config_by_user,
        operator,
        bk_tenant_id=DEFAULT_TENANT_ID,
        unit="",
        default_value=None,
        tag="",
        description="",
        is_reserved_check=True,
        alias_name="",
        option=None,
        is_disabled=False,
    ):
        """
        创建一个新的字段
        :param table_id: 结果表ID
        :param field_name: 字段名
        :param field_type: 字段类型
        :param unit: 字段单位
        :param tag: 字段标签
        :param is_config_by_user: 是否用户定义字段
        :param default_value: 默认值
        :param operator: 创建者
        :param bk_tenant_id: 租户ID
        :param description: 字段描述
        :param is_reserved_check: 是否做保留字段检查
        :param alias_name: 字段别名
        :param option: 字段选项
        :return: True | raise Exception
        """
        if is_reserved_check:
            if field_name.upper() in config.RT_RESERVED_WORD_EXACT:
                logger.error(
                    f"user->[{operator}] try to create field->[{field_name}] which is reserved field, nothing will added."
                )
                raise ValueError(_("字段[%s]为保留字段，不可创建") % field_name)

        if cls.objects.filter(table_id=table_id, field_name=field_name, bk_tenant_id=bk_tenant_id).exists():
            logger.error(
                f"field->[{field_name}] is exists under table->[{table_id}] in bk_tenant_id->[{bk_tenant_id}], nothing will be added."
            )
            raise ValueError(_("字段[{}]已在租户[{}]-表[{}]中存在，请确认").format(field_name, bk_tenant_id, table_id))

        cls.objects.create(
            table_id=table_id,
            field_name=field_name,
            field_type=field_type,
            bk_tenant_id=bk_tenant_id,
            unit=unit,
            tag=tag,
            is_config_by_user=is_config_by_user,
            default_value=default_value,
            creator=operator,
            description=description,
            alias_name=alias_name,
            is_disabled=is_disabled,
        )
        logger.info(
            f"new field->[{field_name}] type->[{field_type}] is create for table->[{table_id}],bk_tenant_id->[{bk_tenant_id}]"
        )

        # 如果不存在option配置，直接返回
        if option is None:
            logger.info(
                f"new field->[{field_name}]  of table_id->[{table_id}],bk_tenant_id->[{bk_tenant_id}],got no option config, jump it."
            )
            return True

        for option_name, option_value in list(option.items()):
            ResultTableFieldOption.create_option(
                table_id=table_id,
                field_name=field_name,
                name=option_name,
                value=option_value,
                creator=operator,
                bk_tenant_id=bk_tenant_id,
            )
            logger.info(
                f"field->[{field_name}] in table->[{table_id}] of bk_tenant_id->[{bk_tenant_id}],now has option->[{option_name}] with value->[{option_value}]"
            )

        return True

    @classmethod
    def get_field_list(cls, table_id, bk_tenant_id=DEFAULT_TENANT_ID, include_default_fields=False):
        """
        获取一个结果表的字段列表
        :param table_id: 结果表ID
        :param bk_tenant_id: 租户ID
        :param include_default_fields: 是否需要包含默认字段
        :return: QuerySet [field_object,  field_object]
        """
        field_list = cls.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)
        if not include_default_fields:
            field_list = field_list.exclude(
                field_name__in=[
                    "bk_biz_id",
                    "bk_supplier_id",
                    "bk_cloud_id",
                    "time",
                    "ip",
                    "bk_cmdb_level_name",
                    "bk_cmdb_level_id",
                    "bk_cmdb_level",
                    "bk_host_id",
                    "bk_agent_id",
                    "bk_target_host_id",
                ]
            )

        return field_list

    def to_json(self, is_consul_config=False):
        result = {
            "field_name": self.field_name,
            "type": self.field_type,
            "tag": self.tag,
            "default_value": self.default_value,
            "is_config_by_user": self.is_config_by_user,  # 是否已被用户确认添加
            "description": _(self.description),
            "unit": _(self.unit),
            "alias_name": _(self.alias_name),
            "option": ResultTableFieldOption.get_field_option(table_id=self.table_id, field_name=self.field_name),
            "is_disabled": self.is_disabled,
        }

        if is_consul_config and self.alias_name != "":
            result["field_name"] = self.alias_name
            result["alias_name"] = self.field_name

        return result

    def to_json_self_only(self, is_consul_config=False):
        """
        仅返回自身相关的信息json格式，其他的内容需要调用方自行追加，目前已知需要用户自定义添加的内容
        1. option, 字段选项内容
        :param is_consul_config:
        :return:
        """

        result = {
            "field_name": self.field_name,
            "type": self.field_type,
            "tag": self.tag,
            "default_value": self.default_value,
            "is_config_by_user": self.is_config_by_user,  # 是否已被用户确认添加
            "description": self.description,
            "unit": self.unit,
            "alias_name": self.alias_name,
            "is_disabled": self.is_disabled,
        }

        # NOTE: 设计如此，因为 transfer 和 metadata 对这两个字段的含义相反
        # 而 transfer 是通过 consul 获取数据，因此，写入 consul 的数据需要处理
        if is_consul_config and self.alias_name != "":
            result["field_name"] = self.alias_name
            result["alias_name"] = self.field_name

        return result

    @classmethod
    def batch_get_fields(
        cls,
        table_id_list: list[str],
        is_consul_config: bool | None = False,
        bk_tenant_id: str | None = DEFAULT_TENANT_ID,
    ) -> dict:
        table_field_option_dict = ResultTableFieldOption.batch_field_option(
            table_id_list=table_id_list, bk_tenant_id=bk_tenant_id
        )

        qs = cls.objects.filter(table_id__in=table_id_list, bk_tenant_id=bk_tenant_id)

        # 组装数据
        data = {}
        for i in qs:
            # 添加对应的 option
            item = {
                "field_name": i.field_name,
                "type": i.field_type,
                "tag": i.tag,
                "default_value": i.default_value,
                "is_config_by_user": i.is_config_by_user,
                "description": i.description,
                "unit": i.unit,
                "alias_name": i.alias_name,
                "option": getitems(table_field_option_dict, [i.table_id, i.field_name], default={}),
                "is_disabled": i.is_disabled,
            }
            if is_consul_config and i.alias_name != "":
                item["field_name"] = i.alias_name
                item["alias_name"] = i.field_name

            # 组装对应的数据
            data.setdefault(i.table_id, []).append(item)
        return data


class ResultTableRecordFormat(models.Model):
    """记录结果表中的维度和指标关系"""

    table_id = models.CharField("结果表名", max_length=128)
    metric = models.CharField("指标字段", max_length=32)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    # 维度字段列表，JSON格式数组，元素为字符串
    dimension_list = models.CharField("维度字段列表", max_length=32, db_index=True)
    is_available = models.BooleanField("是否生效")

    class Meta:
        # 一个结果表不可能有重复的组合信息
        unique_together = ("table_id", "metric", "dimension_list", "bk_tenant_id")
        verbose_name = "结果表字段"
        verbose_name_plural = "结果表字段表"

    @classmethod
    def create_record_format(cls, table_id, metric, dimension_list, bk_tenant_id=DEFAULT_TENANT_ID, is_available=False):
        """
        创建关系记录
        :param table_id: 结果表ID
        :param metric: 指标字段
        :param dimension_list: 维度字段数组，元素为字符串
        :param bk_tenant_id: 租户ID
        :param is_available: 是否需要将该配置生效
        :return: True | raise Exception
        """
        logger.info(
            "create record format for table->[%s] of bk_tenant_id->[%s] metric->[%s] dimension->[%s]",
            table_id,
            bk_tenant_id,
            metric,
            dimension_list,
        )
        # 1. 确认所有的字段都是存在的
        fields_list = copy.copy(dimension_list)
        fields_list.append(metric)

        real_fields_count = ResultTableField.objects.filter(
            field_name__in=fields_list, table_id=table_id, bk_tenant_id=bk_tenant_id
        ).count()

        if real_fields_count != len(fields_list):
            logger.error(
                f"try to set metric->[{metric}] dimension_list->[{dimension_list}] for table->[{bk_tenant_id}] of bk_tenant_id->[{table_id}] but some fields "
                "are missing."
            )
            raise ValueError(_("部分维度或者指标字段不存在，请确认"))

        # 2. 将配置写入，但是不生效
        new_format = cls.objects.create(
            table_id=table_id,
            metric=metric,
            dimension_list=json.dumps(dimension_list),
            bk_tenant_id=bk_tenant_id,
            is_available=False,
        )
        logger.info(
            f"new format for table->[{table_id}] of bk_tenant_id->[{bk_tenant_id}] metric->[{metric}] dimension->[{dimension_list}] is now create."
        )

        # 3. 按需激活该配置
        if is_available:
            new_format.set_metric_available()

        return True

    @atomic(config.DATABASE_CONNECTION_NAME)
    def set_metric_available(self):
        """
        将一个指标字段的维度关系标记为可用的
        :return: True | raise Exception
        """
        # 1. 将已有的所有dimension配置改为不可用
        all_table_formats = self.__class__.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
        all_table_formats.update(is_available=False)
        logger.info(f"all format for table->[{self.table_id}] now is disabled.")

        # 2. 将自己改为可用
        self.is_available = True
        self.save()
        logger.info(
            f"format for metric->[{self.metric}] dimension->[{self.dimension_list}] table->[{self.table_id}] of bk_tenant_id->[{self.bk_tenant_id}] now is available."
        )
        return True


class CMDBLevelRecord(models.Model):
    """
    记录结果表拆解CMDB层级的关系记录
    """

    source_table_id = models.CharField(verbose_name="来源结果表", max_length=128)
    target_table_id = models.CharField(verbose_name="落地结果表", max_length=128)
    bk_data_id = models.IntegerField(verbose_name="数据源配置ID")
    cmdb_level = models.CharField(verbose_name="拆解CMDB的层级名", max_length=255)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    is_disable = models.BooleanField(verbose_name="记录是否已经废弃", default=False)

    # 查询manage
    enable_object = EnableManager()
    objects = models.Manager()

    class Meta:
        # 对于同一个结果表的同一个CMDB的层级拆分，不可以有重复
        unique_together = ("source_table_id", "cmdb_level", "bk_tenant_id")
        verbose_name = "CMDB层级拆分记录"
        verbose_name_plural = "CMDB层级拆分记录表"

    @classmethod
    def is_level_exists(cls, source_table_id, cmdb_level, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        判断一个指定的结果表是否已经存在指定的层级清洗配置
        :param source_table_id: 来源结果表ID
        :param cmdb_level: CMDB层级
        :param bk_tenant_id: 租户ID
        :return: True | False
        """

        return cls.enable_object.filter(
            source_table_id=source_table_id, cmdb_level=cmdb_level, bk_tenant_id=bk_tenant_id
        ).exists()

    @classmethod
    def create_record(
        cls, source_table_id, bk_data_id, cmdb_level, operator, target_table_id=None, bk_tenant_id=DEFAULT_TENANT_ID
    ):
        """
        创建一个新的CMDB层级清理配置
        :param source_table_id: 源结果表名
        :param target_table_id: 目标结果表名，如果不提供则使用结果表和层级配置的方式
        :param bk_data_id: 数据源ID
        :param cmdb_level: CMDB层级名
        :param operator: 操作者
        :param bk_tenant_id: 租户ID
        :return: record_object
        """
        logger.info(
            "CMDBLevelRecord: try to create record for table_id->[%s] of bk_tenant_id->[%s],cmdb_level->[%s]",
            source_table_id,
            bk_tenant_id,
            cmdb_level,
        )
        # 0. 处理源结果表和目标结果表的配置
        source_table = ResultTable.objects.get(table_id=source_table_id, bk_tenant_id=bk_tenant_id)
        if target_table_id is None:
            target_table_id = config.RT_CMDB_LEVEL_RT_NAME.format(source_table_id)

        # 1. 判断源结果表是否已经配置了输出结果
        # 如果后续需要将不同层级放到不同的结果表，可以考虑修改这里的逻辑
        if not cls.enable_object.filter(source_table_id=source_table_id, bk_tenant_id=bk_tenant_id).exists():
            # 如果没有配置，需要增加一个新的结果表
            # 准备对应的结果表字段内容, 查询中去掉了默认字段内容
            field_list = ResultTableField.get_field_list(
                table_id=source_table_id, include_default_fields=False, bk_tenant_id=bk_tenant_id
            )

            # 结果表的字段和源结果表一致，
            field_dict_list = [
                {
                    "field_name": field_info.field_name,
                    "field_type": field_info.field_type,
                    "operator": operator,
                    "is_config_by_user": field_info.is_config_by_user,
                    "tag": field_info.tag,
                }
                for field_info in field_list
            ]

            logger.debug(
                f"result_table->[{target_table_id}] of bk_tenant_id->[{bk_tenant_id}] going to create with field_list->[{field_dict_list}]"
            )

            logger.info(
                f"result_table->[{target_table_id}] of bk_tenant_id->[{bk_tenant_id}] is going to create field count->[{len(field_dict_list)}]"
            )

            # 创建结果表
            ResultTable.create_result_table(
                bk_data_id=bk_data_id,
                table_id=target_table_id,
                bk_tenant_id=bk_tenant_id,
                table_name_zh=source_table.table_name_zh,
                is_custom_table=True,
                schema_type=ResultTable.SCHEMA_TYPE_FREE,
                default_storage=ClusterInfo.TYPE_INFLUXDB,
                operator=operator,
                field_list=field_dict_list,
                # 不同步的原因是，并不知道后续的内容是否会成功
                is_sync_db=False,
                bk_biz_id=source_table.bk_biz_id,
                # 需要将CMDB拆分层级的字段增加上
                include_cmdb_level=True,
            )
            logger.info(
                f"result_table->[{target_table_id}] of bk_tenant_id->[{bk_tenant_id}] datasource->[{bk_data_id}] for cmdb split is create"
            )

        # 3. 增加CMDB拆分记录
        record = cls.objects.create(
            source_table_id=source_table_id,
            target_table_id=target_table_id,
            bk_data_id=bk_data_id,
            bk_tenant_id=bk_tenant_id,
            cmdb_level=cmdb_level,
        )

        # 2. 增加一个新的结果表option配置
        ResultTableOption.sync_cmdb_level_option(table_id=target_table_id, operator=operator, bk_tenant_id=bk_tenant_id)
        logger.info(
            f"target_table_id->[{target_table_id}] of bk_tenant_id->[{bk_tenant_id}] cmdb_level option added success."
        )

        logger.info(
            f"source_rt->[{source_table_id}] of bk_tenant_id->[{bk_tenant_id}] target_rt->[{target_table_id}] for cmdb_level->[{cmdb_level}] via data_id->[{bk_data_id}] is  create "
            "new record"
        )

        return record

    @classmethod
    def get_table_data_source(cls, source_table_id, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        返回一个结果表作为源的数据源
        :param source_table_id: 源结果表
        :param bk_tenant_id: 租户ID
        :return: data_source配置 or None
        """
        query = cls.enable_object.filter(source_table_id=source_table_id, bk_tenant_id=bk_tenant_id)
        # 判断是否存在该配置
        if query.exists():
            return query.first()

        raise cls.DoesNotExist(_("找不到结果表配置"))

    @property
    def source_data_source(self):
        """
        源结果表输出的数据源ID
        :return: data_source配置
        """
        if self.is_disable:
            logger.warning(
                f"source_table_id->[{self.source_table_id}] table_table->[{self.target_table_id}] cmdb_level->[{self.cmdb_level}] is disable, nothing will get"
            )
            raise ValueError(_("结果表配置已失效，请确认后重试"))

        # 这里只可以使用输出结果表的来源数据源来判断data source id
        # 因为输入的结果表可能会输出到多个数据源
        return DataSource.objects.get(bk_data_id=self.bk_data_id)


class ResultTableOption(OptionBase):
    """结果表option配置"""

    QUERY_NAME = "table_id"

    OPTION_CMDB_LEVEL_CONFIG = "cmdb_level_config"
    OPTION_ES_DOCUMENT_ID = "es_unique_field_list"
    OPTION_GROUP_INFO_ALIAS = "group_info_alias"
    OPTION_CUSTOM_REPORT_DIMENSION_VALUES = "dimension_values"
    OPTION_SEGMENTED_QUERY_ENABLE = "segmented_query_enable"
    OPTION_IS_SPLIT_MEASUREMENT = "is_split_measurement"
    OPTION_ENABLE_FIELD_BLACK_LIST = "enable_field_black_list"

    # 选项类型
    TYPE_BOOL = "bool"
    TYPE_STRING = "string"
    TYPE_LIST = "list"

    table_id = models.CharField("结果表ID", max_length=128, db_index=True)
    name = models.CharField(
        "option名称",
        choices=(
            (OPTION_CMDB_LEVEL_CONFIG, OPTION_CMDB_LEVEL_CONFIG),
            (OPTION_ES_DOCUMENT_ID, OPTION_ES_DOCUMENT_ID),
            (OPTION_GROUP_INFO_ALIAS, OPTION_GROUP_INFO_ALIAS),
            (OPTION_CUSTOM_REPORT_DIMENSION_VALUES, OPTION_CUSTOM_REPORT_DIMENSION_VALUES),
            (OPTION_SEGMENTED_QUERY_ENABLE, _("分段查询开关")),
            (OPTION_IS_SPLIT_MEASUREMENT, _("是否为单指标单表")),
            (OPTION_ENABLE_FIELD_BLACK_LIST, _("是否开启指标黑名单")),
        ),
        max_length=128,
    )

    @classmethod
    def batch_result_table_option(cls, table_id_list, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        返回批量的
        :param table_id_list: 结果表ID列表
        :param bk_tenant_id: 租户ID
        :return: {
            'table_id': {
                'option_name': option_value
            }
        }
        禁止跨租户查询
        """
        option_dict = {table_id: {} for table_id in table_id_list}

        for option in cls.objects.filter(table_id__in=table_id_list, bk_tenant_id=bk_tenant_id):
            try:
                option_dict[option.table_id].update(option.to_json())
            except KeyError:
                option_dict[option.table_id] = option.to_json()

        return option_dict

    @classmethod
    def sync_cmdb_level_option(cls, table_id, operator, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        同步CMDB层级拆分的记录，如果之前未有记录，则会创建一个新的
        否则会在已有的记录上更新记录
        :param table_id: 结果表ID
        :param operator: 操作者
        :param bk_tenant_id: 租户ID
        :return: True | raise Exception
        """
        # 确认结果表存在
        ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)

        try:
            record = cls.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)

        except cls.DoesNotExist:
            record = cls(
                table_id=table_id,
                bk_tenant_id=bk_tenant_id,
                name=cls.OPTION_CMDB_LEVEL_CONFIG,
                value_type=cls.TYPE_LIST,
                creator=operator,
                value="[]",
            )

        # 遍历所有的CMDB层级信息，更新option的内容
        value = []
        cmdb_record_list = CMDBLevelRecord.objects.filter(target_table_id=table_id, bk_tenant_id=bk_tenant_id)
        for cmdb_record in cmdb_record_list:
            value.append(cmdb_record.cmdb_level)

        record.value = json.dumps(value)
        record.save()

        logger.info(
            f"result_table->[{table_id}] of bk_tenant_id->[{bk_tenant_id}] cmdb_level option->[{record.id}] is updated to->[{value}]"
        )

        return True

    @classmethod
    def create_option(cls, table_id, name, value, creator, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        创建结果表选项内
        :param table_id: 结果表ID
        :param name: 选项名
        :param value: 选项值
        :param creator: 创建者
        :param bk_tenant_id: 租户ID
        :return: object
        """
        if cls.objects.filter(table_id=table_id, name=name, bk_tenant_id=bk_tenant_id).exists():
            logger.error(
                f"table_id->[{table_id}] of bk_tenant_id->[{bk_tenant_id}] already has option->[{name}], maybe something go wrong?"
            )
            raise ValueError(_("结果表已存在[{}]选项").format(name))

        new_record = cls._create_option(value=value, creator=creator)

        new_record.table_id = table_id
        new_record.name = name
        new_record.bk_tenant_id = bk_tenant_id
        new_record.save()

        logger.info(f"table_id->[{table_id}] of bk_tenant_id->[{bk_tenant_id}] now has create option->[{name}]")

        return new_record

    @classmethod
    def bulk_create_options(
        cls, table_id: str, option_data: dict[str, Any], creator: str, bk_tenant_id=DEFAULT_TENANT_ID
    ):
        """批量创建结果表级别的选项内容

        :param table_id: 结果表ID
        :param option_data: 选项内容, 格式: {name: value}
        :param creator: 创建者
        :param bk_tenant_id: 租户ID
        """
        logger.info(
            "bulk_create_options: try to create options for table_id->[%s] of bk_tenant_id->[%s]",
            table_id,
            bk_tenant_id,
        )
        # 组装写入的对象
        obj_list, option_name_list = [], []
        for option_name, option_value in option_data.items():
            value, value_type = cls._parse_value(option_value)
            item = {
                "table_id": table_id,
                "creator": creator,
                "name": option_name,
                "value": value,
                "value_type": value_type,
                "bk_tenant_id": bk_tenant_id,
            }
            option_name_list.append(option_name)
            obj_list.append(cls(**item))

        if not obj_list:
            logger.info("table_id->[%s] of bk_tenant_id->[%s] options is null", table_id, bk_tenant_id)
            return

        # 判断是否存在
        # NOTE: 如果存在，则抛异常
        existed_name_list = cls.objects.filter(
            table_id=table_id, name__in=option_name_list, bk_tenant_id=bk_tenant_id
        ).values_list("name", flat=True)
        if existed_name_list:
            existed_name_str = ",".join(existed_name_list)
            logger.error(
                "table_id->[%s] of bk_tenant_id->[%s] already has option->[%s], maybe something go wrong?",
                table_id,
                bk_tenant_id,
                existed_name_str,
            )
            raise ValueError(_("结果表已存在[{}]选项").format(existed_name_str))

        # 批量写入数据
        cls.objects.bulk_create(obj_list, batch_size=BULK_CREATE_BATCH_SIZE)

        logger.info(
            "table_id->[%s] of bk_tenant_id->[%s] now has options->[%s]",
            table_id,
            bk_tenant_id,
            json.dumps(option_data),
        )


class ResultTableFieldOption(OptionBase):
    # es_field_type: ES专用，ES存储类型
    OPTION_ES_FIELD_TYPE = "es_type"
    # es_include_in_all: ES专用，存储是否需要包含到_all中
    OPTION_ES_INCLUDE_IN_ALL = "es_include_in_all"
    # es_time_format: ES专用, 时间字段的时间格式，格式样式应该以ES格式为准
    OPTION_ES_TIME_FORMAT = "es_format"
    # es_doc_values: ES专用，字段是否维度字段
    OPTION_ES_DOC_VAVLUES = "es_doc_values"
    # es_index: ES专用，字段是否需要分词，对应值可以为：analyzed、not_analyzed或no
    OPTION_ES_INDEX = "es_index"
    # influxdb_disabled: influxdb专用，表示字段是否不必写入到influxdb
    OPTION_INFLUXDB_DISABLED = "influxdb_disabled"

    # 查询选项名称列表
    QUERY_OPTION_NAME_LIST: list[str] = [
        "need_add_time",  # 是否需要添加时间字段
        "time_field",  # 指定查询时间单位，如：day、hour、minute、second
    ]

    table_id = models.CharField("结果表ID", max_length=128, db_index=True)
    field_name = models.CharField("字段名", max_length=255, db_collation="utf8_bin")
    name = models.CharField(
        "option名称",
        choices=(
            (OPTION_ES_FIELD_TYPE, OPTION_ES_FIELD_TYPE),
            (OPTION_ES_INCLUDE_IN_ALL, OPTION_ES_INCLUDE_IN_ALL),
            (OPTION_ES_TIME_FORMAT, OPTION_ES_TIME_FORMAT),
            (OPTION_ES_DOC_VAVLUES, OPTION_ES_DOC_VAVLUES),
            (OPTION_ES_INDEX, OPTION_ES_INDEX),
            (OPTION_INFLUXDB_DISABLED, OPTION_INFLUXDB_DISABLED),
        ),
        max_length=128,
    )

    @classmethod
    def create_option(cls, table_id, field_name, name, value, creator, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        创建结果表字段选项
        :param table_id: 结果表ID
        :param field_name: 字段名
        :param name: 选项名
        :param value: 值
        :param creator: 创建者
        :param bk_tenant_id: 租户ID
        :return:
        """
        if cls.objects.filter(table_id=table_id, field_name=field_name, name=name, bk_tenant_id=bk_tenant_id).exists():
            logger.error(
                f"table_id->[{table_id}] in bk_tenant_id->[{bk_tenant_id}],field_name->[{field_name}] already has option->[{name}], maybe something go "
                "wrong?"
            )
            raise ValueError(_("结果表字段[{}]已存在[{}]选项").format(field_name, name))

        # 通过父类统一创建基本信息
        record = cls._create_option(value, creator)

        # 补充子类的特殊信息
        record.table_id = table_id
        record.field_name = field_name
        record.name = name
        record.bk_tenant_id = bk_tenant_id

        # 写入到数据库
        record.save()

        return record

    @classmethod
    def bulk_create_options(cls, table_id: str, option_data: list[dict], bk_tenant_id: str = DEFAULT_TENANT_ID):
        """批量写入字段选项

        :param table_id: 结果表ID
        :param option_data: 选项内容, 格式: [{"name": "", "value": ""}]
        :param bk_tenant_id: 租户ID
        """
        # 校验是否已经存在，如果已经存在，则抛出异常
        field_name_list = [i["field_name"] for i in option_data]
        qs = cls.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id, field_name__in=field_name_list).values(
            "field_name", "name"
        )
        # 比对是否存在
        filter_data = [f"{i['field_name']}:{i['name']}" for i in qs]
        option_info = [f"{i['field_name']}:{i['name']}" for i in option_data]
        intersection = set(filter_data) & set(option_info)
        # 如果存在，则抛出异常
        if intersection:
            intersection_str = ",".join(intersection)
            logger.error(
                "table_id->[%s] in bk_tenant_id->[%s], field:option->[%s] already exist, maybe something go wrong?",
                table_id,
                bk_tenant_id,
                intersection_str,
            )
            raise ValueError(_("结果表[{}]已存在[{}]字段选项").format(table_id, intersection_str))

        # 批量写入数据
        obj_list = []
        for option in option_data:
            value, value_type = cls._parse_value(option["value"])
            option["value"] = value
            option["value_type"] = value_type
            option["bk_tenant_id"] = bk_tenant_id
            obj_list.append(cls(**option))

        # 为空时，直接返回
        if not obj_list:
            logger.info("table->[%s],bk_tenant_id->[%s] field option is null", table_id, bk_tenant_id)
            return

        cls.objects.bulk_create(obj_list, batch_size=BULK_CREATE_BATCH_SIZE)

        logger.info(
            "table->[%s],bk_tenant-id->[%s] now has field with option->[%s]",
            table_id,
            bk_tenant_id,
            json.dumps(option_data),
        )

    @classmethod
    def batch_field_option(cls, table_id_list, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        禁止跨租户查询
        返回批量的
        :param table_id_list: 结果表ID列表
        :param bk_tenant_id: 租户ID
        :return: {
            'table_id': {
                'field_name': {
                    'option_name': option_value
                }
            }
        }
        """
        option_dict = {table_id: {} for table_id in table_id_list}

        # 不允许跨租户查询,查询的这批结果表必须是同一个租户的
        for option in cls.objects.filter(table_id__in=table_id_list, bk_tenant_id=bk_tenant_id):
            try:
                option_dict[option.table_id][option.field_name].update(option.to_json())
            except KeyError:
                option_dict[option.table_id][option.field_name] = option.to_json()

        return option_dict

    @classmethod
    def get_field_option(cls, table_id, field_name, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        返回一个指定的option配置内容
        :param table_id: 结果表ID
        :param field_name: 字段名
        :param bk_tenant_id: 租户ID
        :return: {
            "option_name": option_value
        }
        """
        option_dict = {}

        for option_list in cls.objects.filter(table_id=table_id, field_name=field_name, bk_tenant_id=bk_tenant_id):
            option_dict.update(option_list.to_json())

        return option_dict

    @classmethod
    def get_field_option_es_format(cls, table_id, field_name, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        返回一个自定的字段option配置内容，但是返回的格式是符合es mapping使用需求
        :param table_id: 结果表ID
        :param field_name: 字段名
        :param bk_tenant_id: 租户ID
        :return: dict， 符合es mappings的字段配置
        """
        origin_option = cls.get_field_option(table_id=table_id, field_name=field_name, bk_tenant_id=bk_tenant_id)
        es_config = {}

        for config_name, config_value in list(origin_option.items()):
            # 如果一个字段配置不是ES开头的，则跳过不再关注
            if not config_name.startswith("es"):
                continue

            es_config[config_name[3:]] = config_value

        return es_config


class ESFieldQueryAliasOption(BaseModel):
    """
    ES字段关联别名配置
    """

    table_id = models.CharField("结果表名", max_length=128)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    field_path = models.CharField("原始字段路径", max_length=256)
    path_type = models.CharField("路径类型", max_length=128, default="keyword")
    query_alias = models.CharField("查询别名", max_length=256)
    is_deleted = models.BooleanField("是否已删除", default=False)

    @classmethod
    def generate_query_alias_settings(cls, table_id, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        生成指定 table_id 的别名配置
        :param table_id: 结果表ID
        :param bk_tenant_id: 租户ID
        :return: dict -> {query_alias: {"type": "alias", "path": field_path}}
        """
        logger.info("Generating alias configuration for bk_tenant_id->[%s],table_id->[%s]", bk_tenant_id, table_id)
        try:
            # 获取未软删除的所有记录
            alias_records = cls.objects.filter(table_id=table_id, is_deleted=False, bk_tenant_id=bk_tenant_id)

            # 构建结果字典
            alias_config = {
                record.query_alias: {
                    "type": "alias",
                    "path": record.field_path,
                }
                for record in alias_records
            }

            logger.info(
                "Alias configuration generated for bk_tenant_id->[%s],table_id=[%s]: %s",
                bk_tenant_id,
                table_id,
                alias_config,
            )
            return alias_config

        except Exception as e:
            logger.error(
                "Error generating alias configuration for bk_tenant_id->[%s],table_id=[%s]: %s",
                bk_tenant_id,
                table_id,
                str(e),
                exc_info=True,
            )
            raise

    @classmethod
    def generate_alias_path_type_settings(cls, table_id, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        生成指定table_id的别名路径类型配置
        :param table_id: 结果表ID
        :param bk_tenant_id: 租户ID
        :return: dict -> {field_path: path_type}
        """
        try:
            alias_records = cls.objects.filter(table_id=table_id, is_deleted=False, bk_tenant_id=bk_tenant_id)

            # 获取ResultTableField中的所有field_name
            existing_field_names = set(
                ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).values_list(
                    "field_name", flat=True
                )
            )

            path_type_map = {
                record.field_path: {
                    "type": record.path_type,
                }
                for record in alias_records
                if record.field_path
                not in existing_field_names  # 只包括那些field_path不在ResultTableField中作为field_name的记录
            }
            return path_type_map
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error generating alias path type configuration for table_id->[%s],error->[%s]", table_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def manage_query_alias_settings(table_id, query_alias_settings, operator, bk_tenant_id=DEFAULT_TENANT_ID):
        """
        管理ES字段关联别名配置记录（支持一个field_path对应多个alias）
        :param table_id: 结果表ID
        :param query_alias_settings: 用户传入的query_alias_settings列表
        :param operator: 操作者
        :param bk_tenant_id 租户ID
        """
        logger.info(
            "manage_query_alias_settings: try to manage alias settings for table_id->[%s],query_alias_settings->[%s]",
            table_id,
            query_alias_settings,
        )
        # 获取当前数据库中的记录（包括软删除记录）
        existing_records = ESFieldQueryAliasOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)
        existing_map = {(record.field_path, record.query_alias): record for record in existing_records}

        if not query_alias_settings:
            logger.info(
                "manage_query_alias_settings: table_id->[%s] now has no query_alias_settings,will delete old records",
                table_id,
            )
            ESFieldQueryAliasOption.objects.filter(table_id=table_id).update(is_deleted=True)
            return

        # 提取用户传入的数据组合，field_path+query_alias 为唯一组合
        incoming_combinations = {(item["field_name"], item["query_alias"]) for item in query_alias_settings}

        try:
            # 新增或更新记录
            for item in query_alias_settings:
                field_path = item["field_name"]
                query_alias = item["query_alias"]
                path_type = item.get("path_type", "keyword")

                if (field_path, query_alias) in existing_map:
                    # 更新记录
                    record = existing_map[(field_path, query_alias)]
                    record.is_deleted = False  # 重置软删除标记
                    record.path_type = path_type  # 更新 path_type
                    record.updater = operator
                    record.save()
                else:
                    # 新增记录
                    ESFieldQueryAliasOption.objects.create(
                        table_id=table_id,
                        bk_tenant_id=bk_tenant_id,
                        field_path=field_path,
                        query_alias=query_alias,
                        path_type=path_type,  # 设置 path_type
                        creator=operator,
                        is_deleted=False,
                    )

            # 标记未提供的记录为软删除
            for (field_path, query_alias), record in existing_map.items():
                if (field_path, query_alias) not in incoming_combinations and not record.is_deleted:
                    record.is_deleted = True
                    record.updater = operator
                    record.save()
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "manage_query_alias_settings: failed to manage alias settings for table_id->[%s], "
                "query_alias_settings->[%s], error->[%s]",
                table_id,
                query_alias_settings,
                e,
            )
            raise e
