# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import re

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from bkmonitor import models as base_models
from bkmonitor.utils.common_utils import DatetimeEncoder, DictObj, ignored, safe_int
from core.drf_resource import resource
from monitor.constants import STRATEGY_CHOICES

INT_REG = re.compile(r"\d+")


class Component(DictObj):
    """
    组件
    """


class ProcessPort(Component):
    """
    进程端口组件
    """

    def __init__(self, kwargs):
        super(ProcessPort, self).__init__(kwargs)
        self.ports = ProcessPort.extract_ports(self.ports)

    @staticmethod
    def extract_ports(ports):
        """
        解析从 CC 返回的进程端口信息
        """
        if isinstance(ports, list):
            return ports

        if not ports:
            return []

        arr_ports = []
        for port in ports.split(","):
            with ignored(ValueError):
                if "-" in port:
                    start_port = int(port.split("-")[0])
                    end_port = int(port.split("-")[1])
                    arr_ports.extend(list(range(start_port, end_port + 1)))
                else:
                    arr_ports.append(int(port))
        return arr_ports


class BaseDictObj(DictObj):
    @property
    def id(self):
        return self.alarm_type

    @property
    def category(self):
        return self.alarm_type

    @property
    def dummy_category(self):
        return "base_alarm"

    @property
    def real_id(self):
        return self.alarm_type

    @property
    def item(self):
        return self.title

    @property
    def desc(self):
        return _(self.description)

    def gen_select2_option(self):
        return dict(id=self.alarm_type, metric_id=self.alarm_type, item=self.title, text=self.desc, unit="")


class CustomStringIndex(BaseDictObj):
    # 自定义字符型告警
    _ID = "gse_custom_event"

    def __init__(self, kwargs=None):
        if kwargs is None:
            kwargs = dict()
        kwargs.update(
            dict(
                alarm_type=self._ID,
                result_table_id=self._ID,
                title="",
                description=_("自定义字符型"),
                unit="",
            )
        )
        super(CustomStringIndex, self).__init__(kwargs)

    @staticmethod
    def get_custom_str_data_id(cc_biz_id, operator):
        return settings.GSE_CUSTOM_EVENT_DATAID


custom_str_index = CustomStringIndex()


class ProcessPortIndex(BaseDictObj):
    # 进程端口监控
    _ID = "proc_port"

    def __init__(self, kwargs=None):
        if kwargs is None:
            kwargs = dict()
        kwargs.update(
            dict(
                alarm_type=self._ID,
                result_table_id=settings.PROC_PORT_TABLE_NAME,
                title=settings.PROC_PORT_METRIC_NAME,
                description=_("进程端口"),
                unit="",
            )
        )
        super(ProcessPortIndex, self).__init__(kwargs)


proc_port_index = ProcessPortIndex()


class OSRestartIndex(DictObj):
    # 系统重启监控
    _ID = "os_restart"

    def __init__(self, kwargs=None):
        if kwargs is None:
            kwargs = dict()
        kwargs.update(
            dict(
                alarm_type=self._ID,
                result_table_id="system_env",
                title=_("系统重新启动"),
                description=_("系统重新启动"),
                unit="",
            )
        )
        super(OSRestartIndex, self).__init__(kwargs)

    @property
    def id(self):
        return self.alarm_type

    @property
    def category(self):
        return "system_env"

    @property
    def dummy_category(self):
        return "base_alarm"

    @property
    def real_id(self):
        return self.alarm_type

    @property
    def item(self):
        return "uptime"

    @property
    def desc(self):
        return _(self.description)

    def gen_select2_option(self):
        return dict(id=self.alarm_type, metric_id=self.alarm_type, item=self.item, text=self.desc, unit="")


os_restart_index = OSRestartIndex()

AbstractRecordModel = base_models.AbstractRecordModel


class MonitorSource(AbstractRecordModel):
    biz_id = models.IntegerField(verbose_name="业务ID")
    title = models.CharField(max_length=256, verbose_name="监控源名称")
    description = models.TextField(blank=True, default="", null=True, verbose_name="备注")
    src_type = models.CharField(blank=True, default="JA", max_length=64, verbose_name="监控源分类")
    scenario = models.CharField(blank=True, default="custom", max_length=64, verbose_name="监控场景")
    monitor_type = models.CharField(blank=True, default="online", max_length=64, verbose_name="监控分类")
    monitor_target = models.CharField(blank=True, default="custom", max_length=50, verbose_name="监控指标")
    stat_source_type = models.CharField(blank=True, default="BKDATA", max_length=64, verbose_name="统计源分类")
    stat_source_info = models.TextField(blank=True, default="", verbose_name="统计源信息（JSON）")

    class Meta:
        managed = False
        db_table = "ja_monitor"

    @property
    def stat_source_info_dict(self):
        try:
            stat_source_info = json.loads(self.stat_source_info)
            if not isinstance(stat_source_info, dict):
                stat_source_info = {}
        except Exception:
            stat_source_info = {}
        return stat_source_info

    @property
    def generate_config_id(self):
        return self.stat_source_info_dict.get("generate_config_id", 0)

    @property
    def aggregator(self):
        return self.stat_source_info_dict.get("aggregator", "")

    @property
    def monitor_item_list(self):
        return MonitorItem.objects.filter(monitor_id=self.id)

    @property
    def monitor_name(self):
        return self.title

    @property
    def monitor_field_show_name(self):
        """监控指标，页面输出
        TODO
        """
        if self.scenario in ["performance", "base_alarm"]:
            return _(self.monitor_name)
        return resource.commons.get_desc_by_field(self.monitor_result_table_id, self.monitor_field)

    @property
    def monitor_result_table_id(self):
        return self.stat_source_info_dict.get("monitor_result_table_id", "")

    @property
    def original_config(self):
        if "original_config" in self.stat_source_info_dict:
            return self.stat_source_info_dict["original_config"]

    @property
    def conversion(self):
        return self.stat_source_info_dict.get("unit_conversion", 1)

    @property
    def monitor_field(self):
        return self.stat_source_info_dict.get("monitor_field", "")

    @property
    def backend_id(self):
        return self.id

    @property
    def monitor_desc(self):
        return self.description

    @property
    def count_method(self):
        _count_method = self.stat_source_info_dict.get("aggregator", "")
        return _count_method

    @property
    def count_freq(self):
        _count_freq = self.stat_source_info_dict.get("count_freq", "")
        return safe_int(_count_freq)

    @property
    def where_sql(self):
        return self.stat_source_info_dict.get("where_sql", "")


class MonitorItemGroup(AbstractRecordModel):
    biz_id = models.IntegerField(verbose_name="业务ID")
    monitor_id = models.IntegerField(blank=True, default=0, verbose_name="监控源ID")
    monitor_level = models.IntegerField(blank=True, default=3, verbose_name="监控等级")
    monitor_item_id = models.IntegerField(verbose_name="告警策略ID")
    monitor_group_id = models.IntegerField(verbose_name="告警策略组ID")

    class Meta:
        managed = False
        db_table = "ja_monitor_item_group"


class MonitorItem(AbstractRecordModel):
    biz_id = models.IntegerField(verbose_name="业务ID")
    title = models.CharField(max_length=256, verbose_name="监控项名称")
    description = models.TextField(blank=True, default="", verbose_name="备注")
    condition = models.TextField(blank=True, default="", verbose_name="监控范围")
    monitor_level = models.IntegerField(blank=True, default=3, verbose_name="监控等级")
    is_none = models.IntegerField(blank=True, default=0, verbose_name="无数据告警开关")
    is_none_option = models.TextField(blank=True, default="", verbose_name="无数据配置")
    is_recovery = models.BooleanField(default=False, verbose_name="恢复告警开关")
    is_classify_notice = models.BooleanField(default=False, verbose_name="分级告警开关")
    monitor_id = models.IntegerField(blank=True, default=0, verbose_name="监控源ID")
    alarm_def_id = models.IntegerField(blank=True, default=0, verbose_name="告警源ID")

    class Meta:
        managed = False
        db_table = "ja_monitor_item"

    @cached_property
    def condition_config(self):
        return DetectAlgorithmConfig.objects.filter(monitor_item_id=self.id)

    @cached_property
    def monitor(self):
        return MonitorSource.objects.get(id=self.monitor_id)

    @cached_property
    def alarm_def(self):
        return AlarmSource.objects.get(id=self.alarm_def_id)

    def condition_dict(self):
        # 主机监控相关，用于拿告警范围，慎用！！！
        _condition_dict = dict()
        condition = json.loads(self.condition or "[[]]")[0]
        for c in condition:
            if c["method"] != "eq":
                continue
            val = c["value"]
            if isinstance(val, list):
                if c["field"] == "ip":
                    val = [
                        host if isinstance(host, str) else "{}|{}".format(host["ip"], host["bk_cloud_id"])
                        for host in val
                    ]
            else:
                val = [val]
            _condition_dict[c["field"]] = val
        return _condition_dict


class AlarmSource(AbstractRecordModel):
    """
    告警源
    关联
        1个清洗配置
        多个屏蔽策略
        多个收敛策略
        1个汇总策略
        1个处理策略
        1个通知策略
    """

    default_timeout = 40
    biz_id = models.IntegerField(verbose_name="业务ID")
    title = models.CharField(max_length=256, verbose_name="告警名称")
    description = models.TextField(blank=True, default="", verbose_name="备注")
    src_type = models.CharField(blank=True, default="JA", max_length=64, verbose_name="告警源分类")
    alarm_type = models.CharField(blank=True, default="Custom", max_length=64, verbose_name="告警分类")
    scenario = models.CharField(blank=True, default="custom", max_length=64, verbose_name="监控场景")
    monitor_target = models.CharField(blank=True, default="", max_length=64, verbose_name="监控对象")
    source_info = models.TextField(blank=True, default="", verbose_name="告警来源信息")
    condition = models.TextField(blank=True, default="", verbose_name="告警范围")
    timeout = models.IntegerField(blank=True, default=40, verbose_name="超时时间")
    alarm_attr_id = models.CharField(blank=True, default="", max_length=128, verbose_name="监控系统内的监控ID")
    monitor_level = models.IntegerField(blank=True, default=3, verbose_name="监控等级")
    alarm_cleaning_id = models.IntegerField(blank=True, default=0, verbose_name="清洗策略ID")
    alarm_collect_id = models.IntegerField(blank=True, default=0, verbose_name="汇总策略ID")
    alarm_solution_id = models.IntegerField(blank=True, default=0, verbose_name="处理策略ID")
    alarm_notice_id = models.IntegerField(blank=True, default=0, verbose_name="通知策略ID")

    class Meta:
        managed = False
        db_table = "ja_alarm_source"

    @cached_property
    def converge(self):
        try:
            return ConvergeConfig.objects.get(alarm_source_id=self.id).config
        except ConvergeConfig.DoesNotExist:
            return "{}"
        except ConvergeConfig.MultipleObjectsReturned:
            return ConvergeConfig.objects.filter(alarm_source_id=self.id)[0].config

    @property
    def notify(self):
        return self.alarm_notice_config.notify_config

    @property
    def notify_dict(self):
        return json.loads(self.notify or "{}")

    @cached_property
    def monitor_item(self):
        return MonitorItem.objects.get(alarm_def_id=self.id)

    @cached_property
    def alarm_notice_config(self):
        return NoticeConfig.objects.get(id=self.alarm_notice_id)

    @cached_property
    def alarm_solution_config(self):
        try:
            return json.dumps(SolutionConfig.objects.get(id=self.alarm_solution_id).to_dict(), cls=DatetimeEncoder)
        except SolutionConfig.DoesNotExist:
            return "{}"


class DetectAlgorithmConfig(AbstractRecordModel):
    """
    监控算法配置
    与监控项相关的监控算法配置
    """

    config = models.TextField(blank=True, default="", verbose_name="算法配置")
    algorithm_id = models.IntegerField(blank=True, default=0, verbose_name="算法ID")
    monitor_item_id = models.IntegerField(blank=True, default=0, verbose_name="监控项ID")

    class Meta:
        managed = False
        db_table = "ja_detect_algorithm_config"

    @property
    def strategy_option(self):
        return self.config

    @cached_property
    def biz_id(self):
        monitor_item = MonitorItem.objects.get(id=self.monitor_item_id)
        alarm_def = monitor_item.alarm_def
        biz_id = alarm_def.biz_id
        return biz_id

    def get_title(self):
        try:
            condition = MonitorItem.objects.get(id=self.monitor_item_id)
            alarm_def = AlarmSource.objects.filter(id=condition.alarm_def_id)[0]
        except Exception:
            return _("检测算法")
        return _("告警策略(%s)的检测算法") % alarm_def.title

    def gen_strategy_desc(self, unit=""):
        try:
            strategy_id = "%s" % self.algorithm_id
            strategy_option = json.loads(self.config)

            method_dict = {"eq": "=", "gte": "≥", "gt": ">", "lt": "<", "lte": "≤", "neq": "!="}
            if strategy_id == "1000":
                return _("当前值%(cur_val)s阈值:%(threshold)s%(unit)s") % {
                    "cur_val": method_dict.get(strategy_option.get("method", "eq")),
                    "threshold": strategy_option.get("threshold", ""),
                    "unit": unit,
                }
            span_html = _(" 或 ")
            desc = _("指标当前值")
            strategy_desc = {
                "1001": _("较上周同一时刻值"),
                "1002": _("较前一时刻值"),
                "1003": _("较%s天内同一时刻绝对值的均值"),
                "1004": _("较%s个时间点的均值"),
            }
            if strategy_id in ["1001", "1002"]:
                if not (strategy_option.get("ceil", "") or strategy_option.get("floor", "")):
                    return
                desc += strategy_desc[strategy_id]
                if strategy_option.get("ceil", ""):
                    desc += _("上升%s%%") % strategy_option.get("ceil", "")
                    if strategy_option.get("floor", ""):
                        desc += span_html
                if strategy_option.get("floor", ""):
                    desc += _("下降%s%%") % strategy_option.get("floor", "")
            elif strategy_id in ["1003", "1004"]:
                if not (strategy_option.get("ceil", "") or strategy_option.get("floor", "")):
                    return
                if strategy_option.get("ceil", ""):
                    desc += strategy_desc[strategy_id] % strategy_option.get("ceil_interval", "")
                    desc += _("上升%s%%") % strategy_option.get("ceil", "")
                    if strategy_option.get("floor", ""):
                        desc += span_html
                if strategy_option.get("floor", ""):
                    desc += strategy_desc[strategy_id] % strategy_option.get("floor_interval", "")
                    desc += _("下降%s%%") % strategy_option.get("floor", "")
            elif strategy_id == "1005":
                desc += _("-前一时刻值%(method)s过去%(num_of_day)s天内任一天同时刻差值* %(times)s + (%(shock)s)") % {
                    "method": method_dict.get(strategy_option.get("method", "eq")),
                    "num_of_day": strategy_option["interval"],
                    "times": strategy_option["times"],
                    "shock": strategy_option["shock"],
                }
            elif strategy_id == "1006":
                desc += _("%(method)s过去%(num_of_day)s天内同一时刻绝对值* %(ratio)s%% + (%(shock)s)") % {
                    "method": method_dict.get(strategy_option.get("method", "eq")),
                    "num_of_day": strategy_option["interval"],
                    "ratio": strategy_option["ratio"],
                    "shock": strategy_option["shock"],
                }
            elif strategy_id == "1007":
                desc += _("和前一时刻均>=%(threshold)s,且之间差值>=前一时刻值 *%(ratio)s%% + (%(shock)s)") % {
                    "threshold": strategy_option["threshold"],
                    "ratio": strategy_option["ratio"],
                    "shock": strategy_option["shock"],
                }
            elif strategy_id == "4000":
                desc = _("%(num)s分钟内%(method)s%(threshold)s次") % {
                    "num": strategy_option.get("range", ""),
                    "method": method_dict.get(strategy_option.get("method", "eq")),
                    "threshold": strategy_option.get("threshold", ""),
                }
            return desc
        except Exception:
            return _("默认参数")

    def gen_strategy_name(self):
        strategy_id = safe_int(self.algorithm_id)
        strategy_name = STRATEGY_CHOICES.get(strategy_id, "-")
        return strategy_name


class SolutionConfig(AbstractRecordModel):
    """
    关联告警源的告警汇总配置
    """

    title = models.CharField(blank=True, default="", max_length=256, verbose_name="名称")
    description = models.TextField(blank=True, default="", null=True, verbose_name="备注")
    config = models.TextField(blank=True, default="", null=True, verbose_name="配置")
    alarm_source_id = models.IntegerField(blank=True, default=0, verbose_name="告警源id")
    solution_id = models.IntegerField(blank=True, default=0, verbose_name="处理id")
    solution_type = models.CharField(max_length=128, verbose_name="处理类型")
    biz_id = models.IntegerField(blank=True, default=0, verbose_name="业务ID")
    creator = models.CharField(max_length=255, verbose_name="作业创建者")

    class Meta:
        managed = False
        db_table = "ja_alarm_solution_config"


class ConvergeConfig(AbstractRecordModel):
    """
    关联告警源的告警收敛配置
    """

    config = models.TextField(blank=True, default="", null=True, verbose_name="配置")
    alarm_source_id = models.IntegerField(blank=True, default=0, verbose_name="告警源id")
    converge_id = models.IntegerField(blank=True, default=0, verbose_name="收敛id")

    class Meta:
        managed = False
        db_table = "ja_alarm_converge_config"

    @cached_property
    def converge(self):
        return AlarmCollectDef.objects.filter(id=self.converge_id).last()


class AlarmCollectDef(models.Model):
    """
    告警收敛策略
    """

    is_enabled = models.BooleanField(
        "是否启用",
        default=True,
        blank=True,
    )
    is_deleted = models.BooleanField(
        "是否删除",
        default=False,
        blank=True,
    )
    title = models.CharField(max_length=256, verbose_name="名称")
    description = models.TextField(blank=True, default="", null=True, verbose_name="备注")
    config = models.TextField(blank=True, default="", null=True, verbose_name="配置")

    class Meta:
        managed = False
        db_table = "ja_alarm_converge_def"


class NoticeConfig(AbstractRecordModel):
    """
    告警通知策略
    """

    title = models.CharField(max_length=256, verbose_name="名称")
    description = models.CharField(blank=True, default="", max_length=256, null=True, verbose_name="备注")
    notify_config = models.TextField(blank=True, default="{}", verbose_name="配置")
    alarm_start_time = models.TimeField(max_length=32, verbose_name="开始时间")
    alarm_end_time = models.TimeField(max_length=32, verbose_name="结束时间")
    alarm_source_id = models.IntegerField(blank=True, default=0, verbose_name="告警源id")

    class Meta:
        managed = False
        db_table = "ja_alarm_notice_config"


class NoticeGroup(AbstractRecordModel):
    """
    告警通知组
    """

    title = models.CharField(max_length=256, verbose_name="名称")
    description = models.CharField(blank=True, default="", max_length=256, verbose_name="备注")
    biz_id = models.IntegerField(blank=True, default=0, verbose_name="业务")
    group_type = models.IntegerField(blank=True, default=0, verbose_name="通知组类型")
    group_receiver = models.TextField(blank=True, default="", verbose_name="通知组收件人")

    class Meta:
        managed = False
        db_table = "ja_alarm_notice_group"
