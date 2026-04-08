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
from typing import Any, ClassVar, Self

from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.translation import gettext as _

from bkmonitor.utils.request import get_request_username
from metadata import config
from metadata.models.common import Label
from metadata.models.data_source import DataSourceOption, DataSourceResultTable
from metadata.models.result_table import ResultTable, ResultTableOption

"""
base is base class of:
    event: defined in event.py
    time_series: defined in time_series.py
    log: defined of log.py
"""

logger = logging.getLogger("metadata")


class CustomGroupBase(models.Model):
    # model差异动态配置
    GROUP_ID_FIELD: ClassVar[str]
    GROUP_NAME_FIELD: ClassVar[str]

    # 默认存储差异配置
    DEFAULT_STORAGE_CONFIG = {}
    DEFAULT_STORAGE = None

    # 时间字段的配置
    STORAGE_TIME_OPTION = {}
    STORAGE_FIELD_LIST = []

    # 虚拟RT字段配置
    bk_data_id = models.IntegerField(verbose_name="数据源ID", db_index=True)
    # 可能存在公共数据源，但是独立的事件分组，因此先保留
    bk_biz_id = models.IntegerField(verbose_name="业务ID", db_index=True)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    table_id = models.CharField(verbose_name="结果表ID", max_length=128, db_index=True, null=True)
    # 自定义上报速率限制，默认为-1，跟随应用动态调整。如果手动指定，则优先使用使用数据库中的设置
    max_rate = models.IntegerField(verbose_name="上报速率限制", default=-1)
    max_future_time_offset = models.IntegerField(verbose_name="上报最大时间偏移", default=-1)
    # 事件标签，默认是其他类型
    label = models.CharField(verbose_name="事件标签", max_length=128, default=Label.RESULT_TABLE_LABEL_OTHER)
    is_enable = models.BooleanField(verbose_name="是否启用", default=True)
    is_delete = models.BooleanField(verbose_name="是否删除", default=False)
    creator = models.CharField(verbose_name="创建者", max_length=255)
    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    # 是否需要每个指标组单个结果表处理
    is_split_measurement = models.BooleanField("是否需要单个指标单表存储", default=False)

    DEFAULT_DATASOURCE_OPTIONS = [{"name": "flat_batch_key", "value": "data"}]

    class Meta:
        abstract = True

    def get_datasource_options(self):
        return self.DEFAULT_DATASOURCE_OPTIONS + self.datasource_options

    @property
    def datasource_options(self):
        return []

    @property
    def result_table_option(self):
        return {}

    @staticmethod
    def make_table_id(bk_biz_id, bk_data_id, bk_tenant_id: str, table_name: str | None = None) -> str:
        raise NotImplementedError

    def update_metrics(self, metric_info):
        raise NotImplementedError

    def set_table_id_disable(self):
        """
        设置结果表废弃，默认是将相关的公共结果表废弃
        :return: True | False
        """
        # 如果结果表存在，则先修改结果表的启用状态
        for table in ResultTable.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id):
            table.modify(operator=get_request_username(settings.COMMON_USERNAME), is_enable=False)
            table.is_deleted = True
            table.save()
        logger.info("group->[%s] table->[%s] is disabled now.", self.custom_group_name, self.table_id)

    @classmethod
    def default_result_table_options(cls):
        pass

    @classmethod
    def process_default_storage_config(cls, custom_group: Self, default_storage_config: dict[str, Any]):
        pass

    @classmethod
    def pre_check(cls, label: str, bk_data_id: int, custom_group_name: str, bk_biz_id: int, bk_tenant_id: str) -> dict:
        """
        pre check name, label, bk_data_id
        """

        # 确认label是否存在
        if not Label.objects.filter(label_type=Label.LABEL_TYPE_RESULT_TABLE, label_id=label).exists():
            logger.error(f"label->[{label}] is not exists as a rt label")
            raise ValueError(_("标签[{}]不存在，请确认后重试").format(label))

        # 判断同一个data_id是否已经被其他事件绑定了
        if cls.objects.filter(bk_data_id=bk_data_id).exists():
            logger.error("bk_data_id->[{}] is already used by other custom group, use it first?")
            raise ValueError(_("数据源[{}]已经被其他自定义组注册使用，请更换数据源").format(bk_data_id))

        # 判断同一个业务下是否有重名的custom_group_name
        filter_kwargs: dict[str, Any] = {
            cls.GROUP_NAME_FIELD: custom_group_name,
        }
        if cls.objects.filter(
            bk_biz_id=bk_biz_id, bk_tenant_id=bk_tenant_id, is_delete=False, **filter_kwargs
        ).exists():
            logger.error(
                f"biz_id->[{bk_biz_id}] of bk_tenant_id->[{bk_tenant_id}] already has {cls.__name__}->[{cls.GROUP_NAME_FIELD}], should change {custom_group_name} and try again."
            )
            raise ValueError(_("自定义组名称已存在，请确认后重试"))

        return filter_kwargs

    @classmethod
    def _create(
        cls,
        table_id: str | None,
        bk_biz_id: int,
        bk_data_id: int,
        custom_group_name: str,
        label: str,
        operator: str,
        is_split_measurement: bool,
        bk_tenant_id: str,
        max_rate: int = -1,
        **filter_kwargs,
    ) -> tuple[str, Self]:
        """
        create custom log group
        """

        if table_id is None:
            # 如果是公共结果表记录，则需要创建公共结果表ID，否则填充None
            table_id = cls.make_table_id(bk_biz_id, bk_data_id, bk_tenant_id=bk_tenant_id, table_name=custom_group_name)

        custom_group = cls.objects.create(
            bk_data_id=bk_data_id,
            bk_biz_id=bk_biz_id,
            label=label,
            creator=operator,
            last_modify_user=operator,
            is_delete=False,
            is_enable=True,
            table_id=table_id,
            bk_tenant_id=bk_tenant_id,
            is_split_measurement=is_split_measurement,
            max_rate=max_rate,
            **filter_kwargs,
        )
        logger.info(
            f"{cls.__name__}->[{custom_group.custom_group_id}] now is created from data_id->[{bk_data_id}] by operator->[{operator}],bk_tenant_id->[{bk_tenant_id}]"
        )

        return table_id, custom_group

    @classmethod
    def create_custom_group(
        cls,
        bk_data_id,
        bk_biz_id,
        custom_group_name,
        label,
        operator,
        bk_tenant_id: str,
        metric_info_list=None,
        table_id: str | None = None,
        is_builtin=False,
        is_split_measurement=False,
        default_storage_config=None,
        additional_options: dict | None = None,
        data_label: str | None = None,
        bk_biz_id_alias: str | None = None,
    ):
        """
        创建一个新的自定义分组记录
        :param bk_data_id: 数据源ID
        :param bk_biz_id: 业务ID
        :param custom_group_name: 自定义组名称
        :param label: 标签，描述事件监控对象
        :param operator: 操作者
        :param metric_info_list: metric列表
        :param table_id: 需要制定的table_id，否则通过默认规则创建得到
        :param is_builtin: 是否为内置指标
        :param is_split_measurement: 是否需要单指标单表存储，主要针对容器大量指标的情况适配
        :param default_storage_config: 默认存储的配置
        :param additional_options: 附带创建的 ResultTableOption
        :param data_label: 数据标签
        :param bk_tenant_id: 租户ID
        :param bk_biz_id_alias: 业务ID别名
        :return: group object
        """
        # 创建流程：pre_check -> _create -> create_result_table -> 配置更新

        logger.info(
            "create_custom_group: bk_biz_id->[%s],bk_tenant_id->[%s], custom_group_name->[%s], label->[%s], "
            "operator->[%s],default_storage_config->[%s],bk_tenant_id->[%s]",
            bk_biz_id,
            bk_tenant_id,
            custom_group_name,
            label,
            operator,
            default_storage_config,
            bk_tenant_id,
        )

        # 1. 参数检查
        filter_kwargs = cls.pre_check(
            label=label,
            bk_data_id=bk_data_id,
            custom_group_name=custom_group_name,
            bk_biz_id=bk_biz_id,
            bk_tenant_id=bk_tenant_id,
        )

        # 2. 创建group
        table_id, custom_group = cls._create(
            table_id=table_id,
            bk_biz_id=bk_biz_id,
            bk_data_id=bk_data_id,
            custom_group_name=custom_group_name,
            label=label,
            operator=operator,
            is_split_measurement=is_split_measurement,
            bk_tenant_id=bk_tenant_id,
            **filter_kwargs,
        )

        # 3. 遍历创建metric_info_list
        # 如果未有提供metric_info_list，则需要替换为空列表，方便后续的逻辑使用
        final_metric_info_list = metric_info_list
        if metric_info_list is None:
            logger.info(
                f"{cls.__name__}->[{custom_group.custom_group_id}] is created with none metric_info_list are set."
            )
            final_metric_info_list = []

        # 创建一个关联的存储关系
        # 如果是自动分表逻辑，则该表为默认路由表，
        # 如果是旧版自定义上报逻辑，则该表作为该dataid的唯一写入表

        if default_storage_config is not None:
            default_storage_config.update(cls.DEFAULT_STORAGE_CONFIG)
        else:
            default_storage_config = cls.DEFAULT_STORAGE_CONFIG

        cls.process_default_storage_config(custom_group, default_storage_config)

        option = {"is_split_measurement": is_split_measurement}
        option.update(additional_options or {})

        # 4. 清除历史 DataSourceResultTable 数据
        # 这里无需添加租户过滤条件,因为bk_data_id全局唯一,除1001外不存在跨租户场景
        if DataSourceResultTable.objects.filter(bk_data_id=bk_data_id).exists():
            DataSourceResultTable.objects.filter(bk_data_id=bk_data_id).delete()

        ResultTable.create_result_table(
            bk_data_id=custom_group.bk_data_id,
            bk_biz_id=custom_group.bk_biz_id,
            table_id=table_id,
            table_name_zh=custom_group.custom_group_name,
            is_custom_table=True,
            schema_type=ResultTable.SCHEMA_TYPE_FREE,
            operator=operator,
            default_storage=cls.DEFAULT_STORAGE,
            default_storage_config=default_storage_config,
            field_list=cls.STORAGE_FIELD_LIST,
            is_builtin=is_builtin,
            # 自定义上报，都不需要业务属性、云区域、IP等内容，只需要保留时间字段即可
            is_time_field_only=True,
            time_option=cls.STORAGE_TIME_OPTION,
            label=label,
            option=option,
            data_label=data_label,
            bk_tenant_id=bk_tenant_id,
            bk_biz_id_alias=bk_biz_id_alias,
        )

        custom_group.update_metrics(metric_info=final_metric_info_list)
        logger.info(f"{cls.__name__}->[{custom_group.custom_group_id}] object now has created")

        # 4. 需要为datasource增加一个option，否则transfer无法得知需要拆解的字段内容
        for item in custom_group.get_datasource_options():
            DataSourceOption.create_option(bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id, creator="system", **item)

        # 5. 刷新配置到节点管理，通过节点管理下发配置到采集器
        # 目前只在新增组的时候增加了这个配置下发逻辑，更新不影响采集器的配置
        # 改为异步任务，因为节点管理接口会超时，update_subscription接口
        from metadata.task.tasks import refresh_custom_report_config

        refresh_custom_report_config.delay(bk_biz_id=bk_biz_id)

        return custom_group

    def modify_custom_group(
        self,
        operator,
        custom_group_name=None,
        label=None,
        is_enable=None,
        metric_info_list=None,
        field_list=None,
        max_rate=None,
        enable_field_black_list: bool | None = None,
        data_label: str | None = None,
    ):
        """
        修改一个事件组
        :param operator: 操作者
        :param custom_group_name: 自定义分组名
        :param label: 事件组标签
        :param is_enable: 是否启用事件组
        :param metric_info_list: metric信息,
        :param field_list: 需要修改的字段信息
        :param max_rate: 上报最大速率
        :param enable_field_black_list: 是否开启黑名单
        :param data_label: 数据标签
        :return: True or raise
        """
        # 不可修改已删除的事件组
        if self.is_delete:
            logger.error(
                f"op->[{self.__class__.__name__}] try to update the deleted {operator}->[{self.custom_group_id}], but nothing will do."
            )
            raise ValueError(_("自定义组已删除，请确认后重试"))

        is_change = False

        # 分组名修改
        if custom_group_name is not None:
            self.custom_group_name = custom_group_name
            is_change = True
            logger.info(
                f"{self.__class__.__name__}->[{self.custom_group_id}] name is changed to->[{custom_group_name}]"
            )

        # 给分组打新的标签
        if label is not None:
            # 确认label是否存在
            if not Label.objects.filter(label_type=Label.LABEL_TYPE_RESULT_TABLE, label_id=label).exists():
                logger.error(f"label->[{label}] is not exists as a rt label")
                raise ValueError(_("标签[{}]不存在，请确认后重试").format(label))

            self.label = label
            is_change = True
            logger.info(f"{self.__class__.__name__}->[{self.custom_group_id}] now is change to label->[{label}]")

        # 判断是否有修改启用标记位，需要提供了该参数，而且该参数与现有的配置不一致方可配置
        if is_enable is not None and self.is_enable != is_enable:
            self.is_enable = is_enable
            is_change = True
            logger.info(f"{self.__class__.__name__}->[{self.custom_group_id}] has change enable->[{is_enable}]")

        # 判断是否有维度信息的创建/修改
        if metric_info_list is not None:
            self.update_metrics(metric_info_list)
            is_change = True
            logger.info(
                f"{self.__class__.__name__}->[{self.custom_group_id}] has create now metric list->[{len(metric_info_list)}]"
            )

        # 判断是否修改速率
        if max_rate is not None:
            self.max_rate = max_rate
            is_change = True
            logger.info(f"{self.__class__.__name__}->[{self.custom_group_id}] has change max_rate->[{max_rate}]")

        if is_change:
            self.last_modify_user = operator
            self.save()
            logger.info(f"{self.__class__.__name__}->[{self.custom_group_id}] is updated by->[{operator}]")

        # 判断黑白名单是否发生变化
        options: dict[str, Any] | None = None
        if enable_field_black_list is not None:
            current_enable_field_black_list_option = ResultTableOption.objects.filter(
                table_id=self.table_id,
                bk_tenant_id=self.bk_tenant_id,
                name=ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST,
            ).first()
            current_enable_field_black_list_option_value = (
                current_enable_field_black_list_option.get_value() if current_enable_field_black_list_option else None
            )
            if current_enable_field_black_list_option_value != enable_field_black_list:
                # 获取当前结果表的option配置，options的更新必须提供所有option的配置
                options = {
                    option_obj.name: option_obj.get_value()
                    for option_obj in ResultTableOption.objects.filter(
                        table_id=self.table_id,
                        bk_tenant_id=self.bk_tenant_id,
                    )
                }
                options[ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST] = enable_field_black_list
                logger.info(
                    f"{self.__class__.__name__}->[{self.custom_group_id}] has change enable_field_black_list->[{enable_field_black_list}]"
                )

        # 这里之前在split的情况下是不做field_list的更新的 之前的背景是会动态更新指标 而不应该用户去设置指标
        # 但是如果用户需要修改元信息的时候 会出现该接口无法更新的情况 所以这里先去掉这个限制
        if field_list is not None or data_label is not None or options is not None:
            try:
                rt = ResultTable.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
            except ResultTable.DoesNotExist:
                raise ValueError(_("对应结果表不存在"))

            modify_params = {}
            if field_list is not None:
                modify_params.update({"field_list": field_list, "is_time_field_only": True, "is_reserved_check": False})
            if data_label is not None:
                modify_params["data_label"] = data_label
            if options is not None:
                modify_params["option"] = options

            if modify_params:
                rt.modify(operator=operator, **modify_params)

        logger.info(f"{self.__class__.__name__}->[{self.custom_group_id}] update success.")
        return True

    @property
    def custom_group_id(self):
        return getattr(self, self.GROUP_ID_FIELD)

    @property
    def custom_group_name(self):
        return getattr(self, self.GROUP_NAME_FIELD)

    @custom_group_name.setter
    def custom_group_name(self, value):
        setattr(self, self.GROUP_NAME_FIELD, value)

    def remove_metrics(self):
        raise NotImplementedError

    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_custom_group(self, operator):
        """
        删除一个指定的组
        :param operator: 操作者
        :return: True or raise
        """
        # 不可修改已删除的事件组
        if self.is_delete:
            logger.error(
                f"op->[{self.__class__.__name__}] try to update the deleted {operator}->[{self.custom_group_id}], but nothing will do."
            )
            raise ValueError(_("自定义组已删除，请确认后重试"))

        self.remove_metrics()

        # 修改标志位
        self.last_modify_user = operator
        self.is_delete = True
        self.save()

        # 需要标记对应的结果表也是清除的状态
        self.set_table_id_disable()
        logger.info(
            f"{self.__class__.__name__}->[{self.custom_group_id}] set result_table->[{self.table_id}] and mark it delete."
        )

        logger.info(f"{self.__class__.__name__}->[{self.custom_group_id}] now is delete.")

        return True

    @property
    def data_label(self):
        try:
            return ResultTable.objects.get(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).data_label
        except ResultTable.DoesNotExist:
            return ""
