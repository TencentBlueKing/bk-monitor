"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.models import QueryConfigModel, StrategyModel
from bkmonitor.utils.db.fields import JsonField
from constants.strategy import DataTarget
from monitor_web.export_import.constant import (
    ConfigType,
    ImportDetailStatus,
    ImportHistoryStatus,
)
from monitor_web.models import CollectConfigMeta, DataTargetMapping
from monitor_web.models.base import OperateRecordModelBase


class ImportHistory(OperateRecordModelBase):
    STATUS_TYPE_CHOICES = (
        (ImportHistoryStatus.IMPORTED, _lazy("导入完成")),
        (ImportHistoryStatus.IMPORTING, _lazy("导入中")),
    )

    status = models.CharField(max_length=100, choices=STATUS_TYPE_CHOICES, verbose_name="导入状态")
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0)

    @property
    def history_detail(self):
        return_data = dict([("status", self.status), ("detail", {})])
        if self.status == ImportHistoryStatus.IMPORTED:
            import_detail_instances = ImportDetail.objects.filter(history_id=self.id)
            success_count = import_detail_instances.filter(import_status=ImportDetailStatus.SUCCESS).count()
            failed_count = import_detail_instances.filter(import_status=ImportDetailStatus.FAILED).count()
            return_data["detail"].update({"success_count": success_count, "failed_count": failed_count})

        return return_data

    def get_target_type(self):
        def get_strategy_target_type(strategy_instance):
            data_target_map = dict([(DataTarget.HOST_TARGET, "HOST"), (DataTarget.SERVICE_TARGET, "SERVICE")])
            result_table_label = strategy_instance.scenario
            item_instance = QueryConfigModel.objects.filter(strategy_id=strategy_instance.id).first()
            target_type = DataTargetMapping().get_data_target(
                result_table_label, item_instance.data_source_label, item_instance.data_type_label
            )
            return data_target_map[target_type]

        detail_instances = ImportDetail.objects.filter(history_id=self.id, import_status=ImportDetailStatus.SUCCESS)
        if not detail_instances:
            return {"error_msg": _("没有导入成功的配置，无法添加目标")}
        if detail_instances.filter(import_status=ImportDetailStatus.IMPORTING):
            return {"error_msg": _("存在正在导入的配置，无法添加")}

        collect_config_ids = [config.config_id for config in detail_instances.filter(type=ConfigType.COLLECT)]
        strategy_config_ids = [config.config_id for config in detail_instances.filter(type=ConfigType.STRATEGY)]
        collect_target_type = [
            config.target_object_type
            for config in CollectConfigMeta.objects.filter(bk_biz_id=self.bk_biz_id, id__in=collect_config_ids)
        ]
        strategy_target_type = list(
            map(get_strategy_target_type, StrategyModel.objects.filter(id__in=strategy_config_ids))
        )
        monitor_target_type = list(set(collect_target_type + strategy_target_type))
        if len(monitor_target_type) > 1:
            return {"error_msg": _("所选配置的监控目标不一致，无法统一添加")}

        return {"target_type": monitor_target_type[0]}


class ImportDetail(OperateRecordModelBase):
    IMPORT_STATUS_CHOICES = (
        (ImportDetailStatus.IMPORTING, _lazy("导入中")),
        (ImportDetailStatus.SUCCESS, _lazy("导入成功")),
        (ImportDetailStatus.FAILED, _lazy("导入失败")),
    )
    TYPE_CHOICES = (
        (ConfigType.PLUGIN, _lazy("插件配置")),
        (ConfigType.COLLECT, _lazy("采集配置")),
        (ConfigType.STRATEGY, _lazy("策略配置")),
    )

    name = models.CharField(max_length=100, verbose_name="配置名称")
    type = models.CharField(max_length=100, choices=TYPE_CHOICES, verbose_name="配置类型")
    label = models.CharField(max_length=100, blank=True, verbose_name="标签")
    history_id = models.IntegerField(verbose_name="对应的导入历史ID")
    config_id = models.CharField(max_length=100, null=True, verbose_name="生成的配置ID")
    import_status = models.CharField(max_length=100, choices=IMPORT_STATUS_CHOICES, verbose_name="导入状态")
    error_msg = models.TextField(blank=True, verbose_name="文件错误信息")
    parse_id = models.IntegerField(verbose_name="解析ID")


class ImportParse(OperateRecordModelBase):
    TYPE_CHOICES = (
        (ConfigType.PLUGIN, _lazy("插件配置")),
        (ConfigType.COLLECT, _lazy("采集配置")),
        (ConfigType.STRATEGY, _lazy("策略配置")),
        (ConfigType.VIEW, _lazy("视图配置")),
    )
    FILE_STATUS_CHOICES = (
        (ImportDetailStatus.SUCCESS, _lazy("文件检测成功")),
        (ImportDetailStatus.FAILED, _lazy("文件检测失败")),
    )

    name = models.CharField(max_length=100, verbose_name="配置名称")
    type = models.CharField(max_length=100, choices=TYPE_CHOICES, verbose_name="配置类型")
    label = models.CharField(max_length=100, blank=True, verbose_name="标签")
    uuid = models.CharField(max_length=100, verbose_name="文件解析内容对应uuid")
    file_status = models.CharField(max_length=100, choices=FILE_STATUS_CHOICES, verbose_name="是否为正确配置")
    error_msg = models.TextField(blank=True, verbose_name="文件错误信息")
    file_id = models.IntegerField(verbose_name="文件ID")
    config = JsonField(null=True, verbose_name="配置详情")
