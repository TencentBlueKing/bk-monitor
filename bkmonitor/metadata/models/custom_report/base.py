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
from typing import Optional

from django.db import models
from django.db.transaction import atomic
from django.utils.translation import gettext as _

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
    GROUP_ID_FIELD = None
    GROUP_NAME_FIELD = None

    # 默认存储差异配置
    DEFAULT_STORAGE_CONFIG = {}
    DEFAULT_STORAGE = None

    # 时间字段的配置
    STORAGE_TIME_OPTION = {}
    STORAGE_FIELD_LIST = []

    NEED_REFRESH_CONSUL = None

    # 虚拟RT字段配置
    bk_data_id = models.IntegerField(verbose_name="数据源ID", db_index=True)
    # 可能存在公共数据源，但是独立的事件分组，因此先保留
    bk_biz_id = models.IntegerField(verbose_name="业务ID", db_index=True)
    table_id = models.CharField(verbose_name="结果表ID", max_length=128, db_index=True, null=True)
    # 自定义上报速率限制，默认为-1，跟随应用动态调整。如果手动指定，则优先使用使用数据库中的设置
    max_rate = models.IntegerField(verbose_name="上报速率限制", default=-1)
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
    def make_table_id(bk_biz_id, bk_data_id, table_name: str = None) -> str:
        raise NotImplementedError

    def update_metrics(self, metric_info):
        raise NotImplementedError

    def set_table_id_disable(self):
        """
        设置结果表废弃，默认是将相关的公共结果表废弃
        :return: True | False
        """
        ResultTable.objects.filter(table_id=self.table_id).update(is_deleted=True, is_enable=False)
        logger.info("group->[%s] table->[%s] is disabled now.", self.custom_group_name, self.table_id)

    @classmethod
    def default_result_table_options(cls):
        pass

    @classmethod
    def pre_check(cls, label: str, bk_data_id: int, custom_group_name: str, bk_biz_id: int) -> dict:
        """
        pre check name, label, bk_data_id
        """

        # 确认label是否存在
        if not Label.objects.filter(label_type=Label.LABEL_TYPE_RESULT_TABLE, label_id=label).exists():
            logger.error("label->[{}] is not exists as a rt label".format(label))
            raise ValueError(_("标签[{}]不存在，请确认后重试").format(label))

        # 判断同一个data_id是否已经被其他事件绑定了
        if cls.objects.filter(bk_data_id=bk_data_id).exists():
            logger.error("bk_data_id->[{}] is already used by other custom group, use it first?")
            raise ValueError(_("数据源[{}]已经被其他自定义组注册使用，请更换数据源").format(bk_data_id))

        # 判断同一个业务下是否有重名的custom_group_name
        filter_kwargs = {
            cls.GROUP_NAME_FIELD: custom_group_name,
        }
        if cls.objects.filter(bk_biz_id=bk_biz_id, is_delete=False, **filter_kwargs).exists():
            logger.error(
                "biz_id->[{}] already has {}->[{}], should change {} and try again.".format(
                    bk_biz_id, cls.__name__, cls.GROUP_NAME_FIELD, custom_group_name
                )
            )
            raise ValueError(_("自定义组名称已存在，请确认后重试"))

        return filter_kwargs

    @classmethod
    def _create(
        cls,
        table_id: str,
        bk_biz_id: int,
        bk_data_id: int,
        custom_group_name: str,
        label: str,
        operator: str,
        is_split_measurement: bool,
        max_rate: int = -1,
        **filter_kwargs,
    ) -> (str, "CustomGroupBase"):
        """
        create custom log group
        """

        if table_id is None:
            # 如果是公共结果表记录，则需要创建公共结果表ID，否则填充None
            table_id = cls.make_table_id(bk_biz_id, bk_data_id, custom_group_name)

        custom_group = cls.objects.create(
            bk_data_id=bk_data_id,
            bk_biz_id=bk_biz_id,
            label=label,
            creator=operator,
            last_modify_user=operator,
            is_delete=False,
            is_enable=True,
            table_id=table_id,
            is_split_measurement=is_split_measurement,
            max_rate=max_rate,
            **filter_kwargs,
        )
        logger.info(
            "{}->[{}] now is created from data_id->[{}] by operator->[{}]".format(
                cls.__name__, custom_group.custom_group_id, bk_data_id, operator
            )
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
        metric_info_list=None,
        table_id=None,
        is_builtin=False,
        is_split_measurement=False,
        default_storage_config=None,
        additional_options: Optional[dict] = None,
        data_label: Optional[str] = None,
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
        :param is_otlp_lop: 是否为 OTLP 日志
        :param data_label: 数据标签
        :return: group object
        """

        # 1. 参数检查
        filter_kwargs = cls.pre_check(
            label=label, bk_data_id=bk_data_id, custom_group_name=custom_group_name, bk_biz_id=bk_biz_id
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
            **filter_kwargs,
        )

        # 3. 遍历创建metric_info_list
        # 如果未有提供metric_info_list，则需要替换为空列表，方便后续的逻辑使用
        final_metric_info_list = metric_info_list
        if metric_info_list is None:
            logger.info(
                "{}->[{}] is created with none metric_info_list are set.".format(
                    cls.__name__, custom_group.custom_group_id
                )
            )
            final_metric_info_list = []

        # 创建一个关联的存储关系
        # 如果是自动分表逻辑，则该表为默认路由表，
        # 如果是旧版自定义上报逻辑，则该表作为该dataid的唯一写入表

        if default_storage_config is not None:
            default_storage_config.update(cls.DEFAULT_STORAGE_CONFIG)

        else:
            default_storage_config = cls.DEFAULT_STORAGE_CONFIG

        option = {"is_split_measurement": is_split_measurement}
        option.update(additional_options or {})

        # 4. 清除历史 DataSourceResultTable 数据
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
        )

        custom_group.update_metrics(metric_info=final_metric_info_list)
        logger.info("{}->[{}] object now has created".format(cls.__name__, custom_group.custom_group_id))

        # 4. 需要为datasource增加一个option，否则transfer无法得知需要拆解的字段内容
        for item in custom_group.get_datasource_options():
            DataSourceOption.create_option(bk_data_id=bk_data_id, creator="system", **item)

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
        enable_field_black_list=None,
        data_label: Optional[str] = None,
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
                "op->[{}] try to update the deleted {}->[{}], but nothing will do.".format(
                    self.__class__.__name__, operator, self.custom_group_id
                )
            )
            raise ValueError(_("自定义组已删除，请确认后重试"))

        is_change = False

        # 分组名修改
        if custom_group_name is not None:
            self.custom_group_name = custom_group_name
            is_change = True
            logger.info(
                "{}->[{}] name is changed to->[{}]".format(
                    self.__class__.__name__, self.custom_group_id, custom_group_name
                )
            )

        # 给分组打新的标签
        if label is not None:
            # 确认label是否存在
            if not Label.objects.filter(label_type=Label.LABEL_TYPE_RESULT_TABLE, label_id=label).exists():
                logger.error("label->[{}] is not exists as a rt label".format(label))
                raise ValueError(_("标签[{}]不存在，请确认后重试").format(label))

            self.label = label
            is_change = True
            logger.info(
                "{}->[{}] now is change to label->[{}]".format(self.__class__.__name__, self.custom_group_id, label)
            )

        # 判断是否有修改启用标记位，需要提供了该参数，而且该参数与现有的配置不一致方可配置
        if is_enable is not None and self.is_enable != is_enable:
            self.is_enable = is_enable
            is_change = True
            logger.info(
                "{}->[{}] has change enable->[{}]".format(self.__class__.__name__, self.custom_group_id, is_enable)
            )

        # 判断是否有维度信息的创建/修改
        if metric_info_list is not None:
            self.update_metrics(metric_info_list)
            is_change = True
            logger.info(
                "{}->[{}] has create now metric list->[{}]".format(
                    self.__class__.__name__, self.custom_group_id, len(metric_info_list)
                )
            )

        # 判断是否修改速率
        if max_rate is not None:
            self.max_rate = max_rate
            is_change = True
            logger.info(
                "{}->[{}] has change max_rate->[{}]".format(self.__class__.__name__, self.custom_group_id, max_rate)
            )

        if is_change:
            self.last_modify_user = operator
            self.save()
            logger.info("{}->[{}] is updated by->[{}]".format(self.__class__.__name__, self.custom_group_id, operator))

        # 这里之前在split的情况下是不做field_list的更新的 之前的背景是会动态更新指标 而不应该用户去设置指标
        # 但是如果用户需要修改元信息的时候 会出现该接口无法更新的情况 所以这里先去掉这个限制
        rt = None
        if field_list or data_label:
            try:
                rt = ResultTable.objects.get(table_id=self.table_id)
            except ResultTable.DoesNotExist:
                raise ValueError(_("对应结果表不存在"))

        if field_list is not None:
            rt.modify(operator=operator, is_reserved_check=False, is_time_field_only=True, field_list=field_list)

        # 如果有传开启/关闭黑名单，则修改结果表数据，并刷新consul数据，触发transfer更新
        if enable_field_black_list is not None:
            ResultTableOption.objects.filter(
                table_id=self.table_id, name=ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST
            ).update(value=json.dumps(enable_field_black_list))
            logger.info(
                "%s->[%s] has change enable_field_black_list->[%s]",
                self.__class__.__name__,
                self.custom_group_id,
                enable_field_black_list,
            )
            self.NEED_REFRESH_CONSUL = True

        # 只在需要刷新 consul 的时候才进行刷新操作
        if self.NEED_REFRESH_CONSUL:
            from metadata.models import DataSource

            DataSource.objects.get(bk_data_id=self.bk_data_id).refresh_consul_config()

        # 判断是否修改数据标签
        if data_label:
            rt.modify(operator=operator, data_label=data_label)

        logger.info("{}->[{}] update success.".format(self.__class__.__name__, self.custom_group_id))
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
                "op->[{}] try to update the deleted {}->[{}], but nothing will do.".format(
                    self.__class__.__name__, operator, self.custom_group_id
                )
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
            "{}->[{}] set result_table->[{}] and mark it delete.".format(
                self.__class__.__name__, self.custom_group_id, self.table_id
            )
        )

        logger.info("{}->[{}] now is delete.".format(self.__class__.__name__, self.custom_group_id))

        return True

    @property
    def data_label(self):
        try:
            return ResultTable.objects.get(table_id=self.table_id).data_label
        except ResultTable.DoesNotExist:
            return ""
