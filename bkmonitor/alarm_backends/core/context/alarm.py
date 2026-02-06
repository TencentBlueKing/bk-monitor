"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import copy
import json
import logging
import urllib.parse
from typing import Any
from collections.abc import Callable

from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from elasticsearch_dsl import AttrDict

from bkmonitor.aiops.alert.utils import (
    DimensionDrillLightManager,
    RecommendMetricManager,
)
from bkmonitor.aiops.utils import ReadOnlyAiSetting
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.models.aiops import AIFeatureSettings
from bkmonitor.utils import time_tools
from bkmonitor.utils.event_related_info import get_alert_relation_info
from bkmonitor.utils.time_tools import (
    hms_string,
    timestamp2datetime,
    utc2_str,
    utc2localtime,
)
from constants.action import ActionPluginType, ActionSignal, ConvergeType, NoticeWay
from constants.alert import (
    AlertRedirectType,
    CMDB_TARGET_DIMENSIONS,
    EVENT_STATUS_DICT,
    EventStatus,
    EventTargetType,
)
from constants.data_source import DATA_CATEGORY, DataSourceLabel, DataTypeLabel
from constants.apm import ApmAlertHelper
from core.errors.alert import AIOpsFunctionAccessedError

from ...service.converge.shield.shielder import AlertShieldConfigShielder
from . import BaseContextObject
from .utils import context_field_timer

logger = logging.getLogger("fta_action.run")


class Alarm(BaseContextObject):
    """
    告警信息对象
    """

    @cached_property
    def _is_sms_notice(self) -> bool:
        """
        判断是否为短信通知

        短信通知时需要过滤 URL，因为短信内容长度有限且 URL 不便于点击使用。

        注意：self.parent.notice_way 已经过 get_notice_channel() 解析，
        通道前缀（如 "bkchat|sms"）已被去除，此处直接比较纯通知方式即可。

        :return: True 表示短信通知，False 表示其他通知方式
        """
        return getattr(self.parent, "notice_way", None) == NoticeWay.SMS

    @cached_property
    def id(self):
        if self.parent.alert:
            return self.parent.alert.id
        return ""

    @cached_property
    def name(self):
        if self.parent.alert:
            return self.parent.alert.alert_name
        return "--"

    @cached_property
    def level(self):
        return self.parent.alert_level

    @cached_property
    def level_name(self):
        """
        告警级别名称
        """
        return self.parent.level_name

    @cached_property
    def collect_count(self):
        """
        汇总的告警数量
        """
        return len(self.parent.alerts)

    @cached_property
    def is_no_data_alarm(self):
        """
        是否为无数据告警（监控专用）
        """
        return self.parent.alert.is_no_data()

    @cached_property
    def display_type(self):
        if self.is_no_data_alarm:
            return _("发生无数据告警")
        return _("发生告警")

    @cached_property
    def display_dimensions(self):
        """
        非目标维度
        """
        dedupe_fields = ["alert_name", "strategy_id", "target_type", "target", "bk_biz_id"]
        return {d.key: d for d in self.new_dimensions.values() if d.key not in dedupe_fields}

    @cached_property
    def display_targets(self):
        """
        监控目标
        """
        first_alert_common_dimensions = self.parent.alerts[0].common_dimension_tuple

        targets = []
        targets_dict = {}

        for alert in self.parent.alerts:
            # 如果非目标维度不一致，直接跳过
            if first_alert_common_dimensions != alert.common_dimension_tuple:
                continue

            dimensions = {d["key"]: d for d in alert.target_dimensions}
            display_dimensions = []
            for key in CMDB_TARGET_DIMENSIONS:
                if key not in dimensions or key == "bk_cloud_id":
                    # 云区域ID暂时去掉
                    continue
                display_value = dimensions[key].get("display_value") or dimensions[key]["value"]
                if display_value:
                    display_dimensions.append(str(display_value))

            if display_dimensions:
                target_display = ":".join(display_dimensions)
                if target_display in targets_dict:
                    targets_dict[target_display] += 1
                    continue
                targets_dict[target_display] = 1

        for target_display, count in targets_dict.items():
            if count > 1:
                targets.append(f"{target_display}({count})")
                continue
            targets.append(target_display)
        return targets

    @cached_property
    def target_string(self):
        """
        告警目标字符串
        """
        if not self.display_targets:
            return ""

        target_string = ",".join(self.display_targets)

        if self.parent.limit:
            limit_target_string = f"{self.display_targets[0]}...({len(self.display_targets)})"
            if len(limit_target_string.encode("utf-8")) < len(target_string.encode("utf-8")):
                target_string = limit_target_string

        return target_string

    @cached_property
    def target_display(self):
        try:
            return getattr(self.parent.alert.event, "target", "")
        except BaseException as error:
            # 直接返回错误信息
            return str(error)

    @cached_property
    def dimensions(self):
        """
        维度字典
        """
        if self.parent.alert and self.parent.alert.origin_alarm:
            return {
                key: AttrDict(dimension)
                for key, dimension in self.parent.alert.origin_alarm["dimension_translation"].items()
            }
        return {}

    @cached_property
    def new_dimensions(self):
        """
        维度字典
        """
        strategy_dimensions = getattr(self.parent.action, "dimensions", [])
        if strategy_dimensions:
            # 默认从当前处理事件获取维度信息，如果不存在，则从alert获取
            return {
                dimension["key"]: dimension if isinstance(dimension, AttrDict) else AttrDict(dimension)
                for dimension in strategy_dimensions
            }
        if self.parent.alert:
            return {dimension.key: dimension for dimension in self.parent.alert.dimensions}
        return {}

    @cached_property
    def origin_dimensions(self):
        if self.parent.alert and self.parent.alert.origin_alarm:
            return self.parent.alert.origin_alarm["data"]["dimensions"]
        return {}

    @cached_property
    def dimension_string(self):
        """
        告警维度字符串
        """
        dimension_string = ",".join(self.dimension_string_list)

        if self.parent.limit:
            limit_dimension_string = f"{self.display_dimensions[0]}..."
            if len(limit_dimension_string.encode("utf-8")) < len(dimension_string.encode("utf-8")):
                dimension_string = [limit_dimension_string]

        return dimension_string

    @cached_property
    def dimension_string_list(self):
        if not self.display_dimensions:
            return []

        # 拓扑维度特殊处理
        display_dimensions = copy.deepcopy(self.display_dimensions)

        dimension_lists = []
        if self.parent.alert.agg_dimensions:
            # 当存在agg_dimensions的顺序列表是，直接使用
            for dimension_key in self.parent.alert.agg_dimensions:
                dimension_key = dimension_key[5:] if dimension_key.startswith("tags.") else dimension_key
                dimension = display_dimensions.pop(dimension_key, None)
                if not dimension:
                    continue
                dimension_lists.append(
                    [dimension.display_key or dimension_key, dimension.display_value or dimension.value or "--"]
                )

        # 如果维度不在agg dimensions中，直接添加在最后
        for dimension_key, dimension in display_dimensions.items():
            dimension_lists.append(
                [dimension.display_key or dimension_key, dimension.display_value or dimension.value or "--"]
            )

        sep: str = "="
        # 如果是 markdown 类型的通知方式，维度值是url，需要转换为链接格式
        if self.parent.notice_way in settings.MD_SUPPORTED_NOTICE_WAYS:
            sep = ": "
            for dimension_list in dimension_lists:
                value: str = str(dimension_list[1]).strip()
                if value.startswith("http://") or value.startswith("https://"):
                    dimension_list[1] = f"[{value}]({value})"

        try:
            dimension_str = [f"{k}{sep}{v}" for k, v in sorted(dimension_lists, key=lambda x: x[0])]
        except Exception:
            dimension_str = [f"{k}{sep}{v}" for k, v in dimension_lists]

        return dimension_str

    @cached_property
    def chart_image(self):
        """
        邮件和微信出图
        """
        from .chart import get_chart_by_origin_alarm

        if not settings.GRAPH_RENDER_SERVICE_ENABLED or not self.parent.strategy.strategy_id:
            return None

        if not self.chart_image_enabled:
            # 不允许出图的策略，直接返回None
            return None

        if self.parent.converge_type != ConvergeType.ACTION:
            # 不允许
            return None

        # 无数据告警，不需要出图
        if self.is_no_data_alarm:
            return None

        strategy = self.parent.strategy
        alert = self.parent.alert
        chart = None
        if getattr(self.parent, "notice_way", None) == "wxwork-bot":
            title = f"{self.parent.strategy.name} - {self.parent.action.id}"
        else:
            title = strategy.items[0].name if strategy.items else "--"

        item = strategy.items[0]
        unify_query = item.query
        action_id = self.parent.action.id if self.parent.action else "None"

        # 无法出图的数据源
        if (
            (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT) in item.data_source_types
            or (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT) in item.data_source_types
            or (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT) in item.data_source_types
        ):
            return

        try:
            # 数据维度过滤
            for data_source in unify_query.data_sources:
                # 数据维度的字段可能比单个 datasource 中的维度字段多，所以需要过滤。
                # promql 的情况下，维度无法分辨，因此只能使用 origin_alarm 中的数据维度
                if data_source.data_source_label == DataSourceLabel.PROMETHEUS:
                    dimension_fields = alert.extra_info.origin_alarm.data.dimension_fields
                else:
                    dimension_fields = data_source.group_by

                for key in self.origin_dimensions:
                    if key not in dimension_fields:
                        continue
                    if self.origin_dimensions[key] is None:
                        continue
                    data_source.filter_dict[key] = self.origin_dimensions[key]

            # 若告警状态为Abnormal，则alert_time为alert.latest_time，否则为alert.end_time
            if alert.status == EventStatus.ABNORMAL:
                alert_time = alert.latest_time
            else:
                alert_time = alert.end_time
            chart = get_chart_by_origin_alarm(
                strategy.items[0],
                timestamp2datetime(alert_time),
                title,
            )
        except Exception as e:
            logger.exception(f"action({action_id}) of alert({self.id}) create alarm chart error, {e}")

        if chart:
            logger.info(f"action({action_id}) of alert({self.id}) create alarm chart success")

        return chart

    @cached_property
    def chart_image_enabled(self):
        """
        是否允许发送图片，默认为True
        """
        return self.parent.strategy.notice.get("options", {}).get("chart_image_enabled", True)

    @cached_property
    def chart_name(self):
        """
        图片名
        """
        if self.chart_image:
            return f"alarm_chart_{self.parent.action.id}.png"
        return ""

    @cached_property
    def attachments(self):
        attachment = []
        try:
            if self.chart_image:
                attachment.append(
                    {"filename": self.chart_name, "content_id": self.chart_name, "content": self.chart_image}
                )
        except BaseException as error:
            logger.exception(
                "get chart_image  of alert(%s) failed, error(%s)",
                self.parent.alert.id if self.parent.alert else "None",
                str(error),
            )

        return attachment

    @cached_property
    def time(self):
        if self.parent.alert:
            return utc2localtime(self.parent.alert.create_time)
        return "--"

    @cached_property
    def begin_time(self):
        return time_tools.utc2localtime(self.parent.alert.begin_time) if self.parent.alert else "--"

    @cached_property
    def begin_timestamp(self):
        return self.parent.alert.begin_time if self.parent.alert else 0

    @cached_property
    def duration(self):
        """
        事件持续时间
        """
        return self.parent.alert.duration or 60 if self.parent.alert else 0

    @cached_property
    def duration_string(self):
        """
        持续时间字符串
        :return:
        """
        if self.parent.alert.latest_time == self.parent.alert.first_anomaly_time:
            return None
        return hms_string(self.duration)

    @cached_property
    def current_value(self):
        """
        事件当前异常值
        """
        # 无数据告警不返回当前值
        if self.is_no_data_alarm:
            return None
        if self.parent.alert.status == EventStatus.RECOVERED:
            return getattr(self.parent.alert.extra_info, "recovery_value", None)
        try:
            return self.parent.anomaly_record.extra_info.origin_alarm.data.value
        except Exception as e:
            logger.info(
                "action(%s) get current value error: %s", self.parent.action.id if self.parent.action else "", e
            )
            return None

    @cached_property
    def detail_url(self):
        """
        告警详情链接, 告警url
        """
        # 短信通知时不返回 URL
        if self._is_sms_notice:
            return None
        if self.parent.is_external_channel:
            # 如果有channel信息，并且不是内部渠道，直接忽略链接
            return None
        if getattr(self.parent, "notice_way", None) in settings.ALARM_MOBILE_NOTICE_WAY and settings.ALARM_MOBILE_URL:
            url = settings.ALARM_MOBILE_URL
        else:
            url = settings.EVENT_CENTER_URL
        # collect_id 为兼容当前前监控版本的id
        return url.format(
            bk_biz_id=self.parent.business.bk_biz_id,
            action_id=self.parent.collect_id,
            collect_id=self.parent.collect_id,
        )

    @cached_property
    def example_detail_url(self):
        """代表单个告警的url"""
        # 短信通知时不返回 URL
        if self._is_sms_notice:
            return None
        if self.parent.is_external_channel:
            # 如果有channel信息，并且不是内部渠道，直接忽略链接
            return None

        if getattr(self.parent, "notice_way", None) in settings.ALARM_MOBILE_NOTICE_WAY and settings.ALARM_MOBILE_URL:
            url = settings.ALARM_MOBILE_URL
        else:
            url = settings.EVENT_CENTER_URL
        # collect_id 为兼容当前前监控版本的id
        return url.format(
            bk_biz_id=self.parent.business.bk_biz_id,
            action_id=self.parent.example_action.es_action_id,
            collect_id=self.parent.example_action.es_action_id,
        )

    @cached_property
    def operate_allowed(self):
        """
        是否允许操作
        """
        if self.parent.is_external_channel or self.parent.followed:
            # 如果有channel信息，并且不是内部渠道，直接忽略链接
            # 如果有关注人，也不出现
            return False
        return True

    @cached_property
    def quick_ack_url(self):
        detail_url = self.detail_url
        return f"{detail_url}&batchAction=ack" if self.operate_allowed and detail_url else None

    @cached_property
    def quick_shield_url(self):
        if not self.operate_allowed:
            # 如果有channel信息，并且不是内部渠道，直接忽略链接
            return None
        if self.collect_count > 1:
            # 当有汇总的告警多余1个的时候，直接返回空
            return None
        detail_url = self.detail_url
        return f"{detail_url}&batchAction=shield" if detail_url else None

    @cached_property
    def notice_from(self):
        return _("蓝鲸监控")

    @cached_property
    def company(self):
        return ""

    @cached_property
    def data_source_name(self):
        """
        数据来源名称
        TODO: 手动执行产生的怎么算呢？
        """
        if not self.parent.strategy.id:
            return "--"
        try:
            item = self.parent.strategy.items[0]
        except BaseException:
            return "--"

        data_source_label = item.data_source_label
        data_type_label = item.data_type_label

        for category in DATA_CATEGORY:
            if category["data_source_label"] == data_source_label and category["data_type_label"] == data_type_label:
                return category["name"]

        return f"{data_source_label}_{data_type_label}"

    @cached_property
    def target_type(self):
        """
        监控目标类型
        """
        if self.parent.alert:
            return self.parent.alert.event.target_type
        return "--"

    @cached_property
    def target_type_name(self):
        """
        监控目标名称
        """
        return {EventTargetType.HOST: "IP", EventTargetType.SERVICE: _("实例"), EventTargetType.TOPO: _("节点")}.get(
            self.target_type, self.target_type
        )

    @cached_property
    def related_info(self):
        """
        关联信息
        """
        return (self.topo_related_info + self.log_related_info) or "--"

    @cached_property
    def topo_related_info(self):
        # CMDB 拓扑层级相关联信息
        host = self.parent.target.host
        if host:
            topo_string = "{}({}) {}({})".format(_("集群"), host.set_string, _("模块"), host.module_string)
            if getattr(host, "bk_env_string", ""):
                topo_string += " {}({})".format(_("环境类型"), host.bk_env_string)
            return topo_string

        return ""

    @cached_property
    def log_related_info(self):
        try:
            return get_alert_relation_info(self.parent.alert)
        except Exception as err:
            logger.exception("Get alert relation info err, msg is %s", err)
        return ""

    @cached_property
    def log_raw_related_info(self):
        try:
            return get_alert_relation_info(self.parent.alert, length_limit=False)
        except Exception as err:
            logger.exception("Get alert relation info err, msg is %s", err)
        return ""

    @cached_property
    def description(self):
        if self.end_description:
            # 如果有恢复信息，直接返回恢复内容
            return self.end_description

        duration_message = _("新告警")
        if self.duration_string:
            duration_message = _("已持续{}").format(self.duration_string)

        message = "{}, {}".format(duration_message, getattr(self.parent.alert.event, "description", ""))
        return message

    @cached_property
    def end_description(self):
        if self.parent.alert is None or self.parent.alert.status == EventStatus.ABNORMAL:
            return None
        return getattr(
            self.parent.alert.extra_info,
            "end_description",
            _("当前告警{}").format(EVENT_STATUS_DICT[self.parent.alert.status]),
        )

    @cached_property
    def is_shielded(self):
        # 获取的时候重新计算是否屏蔽
        shield_result = False
        if self.parent.alert:
            shielder = AlertShieldConfigShielder(self.parent.alert)
            shield_result = shielder.is_matched()
        return shield_result

    @cached_property
    def callback_message(self):
        """
        接口回调数据
        :return:
        """
        alert = self.parent.alert
        if not alert:
            return json.dumps({})

        event = alert.event.to_dict()
        anomaly_record = {
            "anomaly_id": event["id"],
            "source_time": utc2_str(event["time"]),
            "create_time": utc2_str(event["create_time"]),
            "origin_alarm": event.get("extra_info", {}).get("origin_alarm", {}),
        }

        strategy = self.parent.strategy.config or alert.strategy or {}
        biz = self.parent.target.business

        data_source_names = {
            "bk_monitor": _("监控平台"),
            "bk_log_search": _("日志平台"),
            "bk_data": _("计算平台"),
            "custom": _("用户自定义"),
        }

        data_type_names = {
            "log": _("日志关键字"),
            "event": _("事件"),
            "time_series": _("时序"),
        }
        try:
            alert_relation_info = get_alert_relation_info(alert)
        except Exception as e:
            logger.exception(f"get alert[{alert.id}] relation info error: {e}")
            alert_relation_info = "Get relation info error, please contact the administrator"

        items = []
        agg_dimensions = []
        for item in strategy.get("items", []):
            for query_config in item["query_configs"]:
                items.append(
                    {
                        "metric_field": query_config["metric_id"].split(".")[-1],
                        "metric_field_name": item["name"],
                        "data_source_label": query_config["data_source_label"],
                        "data_source_name": data_source_names.get(query_config["data_source_label"], _("其他")),
                        "data_type_label": query_config["data_type_label"],
                        "data_type_name": data_type_names.get(query_config["data_type_label"], _("其他")),
                        "metric_id": query_config["metric_id"],
                    }
                )
                if len(query_config.get("agg_dimensions", [])) > len(agg_dimensions):
                    agg_dimensions = query_config.get("agg_dimensions", [])

        origin_alarm = alert.origin_alarm or {}

        if self.parent.action and self.parent.action.action_plugin["plugin_type"] == ActionPluginType.MESSAGE_QUEUE:
            # 消息队列有信号名称需要特殊处理
            signal_mapping = ActionSignal.MESSAGE_QUEUE_OPERATE_TYPE_MAPPING
        else:
            signal_mapping = ActionSignal.ACTION_SIGNAL_MAPPING

        action_signal = self.parent.action.signal if self.parent.action else ActionSignal.MANUAL
        action_info = {
            # 类型为操作时间的类型
            "type": signal_mapping.get(action_signal, ActionSignal.MANUAL),
            "scenario": strategy.get("scenario"),
            "bk_biz_id": event["bk_biz_id"],
            "bk_biz_name": biz.bk_biz_name,
            "event": {
                "id": alert.id,
                "event_id": alert.id,
                "is_shielded": self.is_shielded,
                "begin_time": utc2_str(alert.begin_time),
                "create_time": utc2_str(alert.create_time),
                "end_time": utc2_str(alert.end_time) if alert.end_time else None,
                "level": self.parent.alert_level,
                "level_name": self.parent.level_name,
                "agg_dimensions": alert.agg_dimensions or agg_dimensions,
                "dimensions": origin_alarm.get("data", {}).get("dimensions"),
                "dimension_translation": origin_alarm.get("dimension_translation"),
            },
            "strategy": {
                "id": strategy.get("id") or None,
                "name": strategy.get("name") or "",
                "scenario": strategy.get("scenario") or None,
                "item_list": items,
            },
            "latest_anomaly_record": anomaly_record,
            "current_value": self.current_value,
            "description": self.description,
            "related_info": alert_relation_info,
            "labels": strategy.get("labels", []),
        }
        return json.dumps(action_info)

    @cached_property
    def alert_info(self):
        alert = self.parent.alert
        if not alert:
            return json.dumps({})

        alert_dict = copy.deepcopy(alert.to_dict())
        extra_info = alert_dict.pop("extra_info", None)
        alert_dict.update({"strategy": extra_info.get("strategy") if extra_info else {}})
        alert_dict["event"].pop("extra_info", None)
        alert_dict["is_shielded"] = self.is_shielded
        alert_dict.update({"current_value": self.current_value, "description": self.description})

        # 日志或事件关联信息
        alert_dict["log_related_info"] = self.log_related_info
        # 整体关联信息，包含了CMDB 和 日志信息
        alert_dict["related_info"] = self.related_info
        return json.dumps(alert_dict)

    @cached_property
    def bkm_info(self):
        alert = self.parent.alert
        if not alert:
            return json.dumps({})

        event = alert.event.to_dict()
        try:
            extra_info = json.loads(event["extra_info"]["origin_alarm"]["data"]["values"]["extra_info"])
        except Exception:
            extra_info = {}
        return extra_info

    @cached_property
    def strategy_url(self):
        # 短信通知时不返回 URL
        if self._is_sms_notice:
            return None
        if self.parent.is_external_channel:
            return None

        if not self.parent.strategy.id:
            return ""

        return f"{settings.BK_MONITOR_HOST}?bizId={self.parent.alert.event.bk_biz_id}#/strategy-config/detail/{self.parent.strategy.id}"

    @cached_property
    def assignees(self):
        if not self.parent.alert:
            return ""
        return ",".join(self.parent.alert.assignee)

    @cached_property
    def receivers(self):
        """
        通知人列表
        从 alert.assignee 获取，alert 是 AlertDocument 实例，存储在 ES (Elasticsearch) 中
        assignee 字段在告警分派时设置，存储在 ES 的 AlertDocument 中
        """
        if not self.parent.alert:
            return []
        return self.parent.alert.assignee or []

    @cached_property
    def appointees(self):
        """
        负责人列表
        """
        if not self.parent.alert:
            return []
        return self.parent.alert.appointee or []

    @cached_property
    def ack_operator(self):
        if not self.parent.alert:
            return ""
        if len(self.ack_operators) == 1:
            return self.parent.alert.ack_operator
        else:
            return _("{}等").format(self.parent.alert.ack_operator)

    @cached_property
    def ack_operators(self):
        if not self.parent.alert:
            return ""
        return [alert.ack_operator for alert in self.parent.alerts if alert.ack_operator]

    @cached_property
    def ack_reason(self):
        if not self.parent.alert:
            return None

        ack_logs = AlertLog.get_ack_logs([alert.id for alert in self.parent.alerts])
        ack_messages = []
        for ack_log in ack_logs:
            ack_messages.append(ack_log.description)
        return ack_messages

    @cached_property
    def ack_title(self):
        if not self.collect_count:
            return None

        if self.collect_count == 1:
            return _("{ack_operator}已确认告警【{alert_name}】").format(
                ack_operator=self.ack_operator, alert_name=self.parent.alert.alert_name
            )

        return _("{ack_operator}已确认【{alert_name}】等{count}个告警").format(
            ack_operator=self.ack_operator, alert_name=self.parent.alert.alert_name, count=self.collect_count
        )

    @cached_property
    def latest_assign_group(self):
        if not self.parent.alert:
            return None
        extra_info = self.parent.alert.extra_info.to_dict()
        return extra_info.get("matched_rule_info", {}).get("group_info", {}).get("group_id")

    @cached_property
    def assign_detail(self):
        # 短信通知时不返回 URL
        if self._is_sms_notice:
            return None
        if not self.latest_assign_group:
            # 最近一次没有的话，表示没有命中分派
            return None
        route_path = base64.b64encode(f"#/alarm-dispatch?group_id={self.latest_assign_group}".encode()).decode("utf8")
        return urllib.parse.urljoin(
            settings.BK_MONITOR_HOST,
            f"route/?bizId={self.parent.business.bk_biz_id}&route_path={route_path}",
        )

    @cached_property
    def is_abnormal(self):
        if self.parent.alert and self.parent.alert.status == EventStatus.ABNORMAL:
            return True
        return False

    @cached_property
    def ai_setting_config(self) -> dict[str, dict[str, Any]] | None:
        try:
            return AIFeatureSettings.objects.get(bk_biz_id=self.parent.alert.event["bk_biz_id"]).config
        except AIFeatureSettings.DoesNotExist:
            return None

    @cached_property
    @context_field_timer
    def anomaly_dimensions(self):
        if not self.parent.alert:
            return None
        try:
            result = DimensionDrillLightManager(
                self.parent.alert, ReadOnlyAiSetting(self.parent.alert.event["bk_biz_id"], self.ai_setting_config)
            ).fetch_aiops_result()
        except AIOpsFunctionAccessedError:
            # 功能未开启通过指标暴露，不额外打日志
            raise
        except Exception as e:
            logger.exception(
                f"alert({self.parent.alert.id})-action("
                f"{self.parent.action.id if self.parent.action else ''}) aiops维度下钻接口请求异常: {e}"
            )
            raise

        anomaly_dimension_count = result["info"]["anomaly_dimension_count"]
        anomaly_dimension_value_count = result["info"]["anomaly_dimension_value_count"]
        return f"异常维度 {anomaly_dimension_count}，异常维度值 {anomaly_dimension_value_count}"

    @cached_property
    @context_field_timer
    def recommended_metrics(self):
        if not self.parent.alert:
            return None
        try:
            result = RecommendMetricManager(
                self.parent.alert, ReadOnlyAiSetting(self.parent.alert.event["bk_biz_id"], self.ai_setting_config)
            ).fetch_aiops_result()
        except AIOpsFunctionAccessedError:
            # 功能未开启通过指标暴露，不额外打日志
            raise
        except Exception as e:
            logger.exception(
                f"alert({self.parent.alert.id})-action("
                f"{self.parent.action.id if self.parent.action else ''}) aiops关联指标接口请求异常: {e}"
            )
            raise
        # 推荐指标维度数
        recommended_metric_dimension_count = result["info"]["recommended_metric_count"]
        # 推荐指标数
        recommended_metric_count = 0
        for recommended_metric in result["recommended_metrics"]:
            recommended_metric_dimension_count += len(recommended_metric.get("metrics", []))
        return f"{recommended_metric_count} 个指标,{recommended_metric_dimension_count} 个维度"

    @cached_property
    def link_layouts(self):
        # 模块链接，先回退
        return []

    @cached_property
    def redirect_types(self) -> list[str]:
        redirect_types: list[str] = [AlertRedirectType.DETAIL.value]
        alert: AlertDocument = self.parent.alert
        if not alert.strategy:
            return redirect_types

        item = alert.strategy["items"][0]
        query_configs = item["query_configs"]
        if not query_configs:
            return redirect_types

        data_source: tuple[str, str] = (query_configs[0]["data_source_label"], query_configs[0]["data_type_label"])
        redirect_map: dict[str, list[tuple[str, str]]] = {
            "log_search": [(DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG)],
            # 事件检索，用于自定义事件和日志关键字场景。
            "event_explore": [
                (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
                (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
            ],
            "query": [
                (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
                (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
                (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES),
                (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
                (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
            ],
        }

        for _type, target in redirect_map.items():
            if data_source in target:
                redirect_types.append(_type)
                break

        # RPC 场景下的自定义指标类型，显示「调用分析」和 APM 自定义「指标检索」
        if ApmAlertHelper.is_rpc_custom_metric(alert.strategy):
            redirect_types.extend([AlertRedirectType.APM_RPC.value, AlertRedirectType.APM_QUERY.value])
        # RPC 场景下的非自定义指标类型，显示「调用分析」和「Tracing 检索」
        elif ApmAlertHelper.is_rpc_system(alert.strategy):
            # TODO 后续有其他明确场景，可在此处补充识别。
            redirect_types.extend([AlertRedirectType.APM_RPC.value, AlertRedirectType.APM_TRACE.value])

        return redirect_types

    @cached_property
    def redirect_infos(self) -> list[dict[str, Any]]:
        # 懒加载模式，按需获取。
        url_getters: dict[str, Callable[[], str | None]] = {
            AlertRedirectType.DETAIL.value: lambda: self.detail_url,
            AlertRedirectType.LOG_SEARCH.value: lambda: self.log_search_url,
            AlertRedirectType.EVENT_EXPLORE.value: lambda: self.event_explore_url,
            AlertRedirectType.QUERY.value: lambda: self.query_url,
            AlertRedirectType.APM_QUERY.value: lambda: self.apm_query_url,
            AlertRedirectType.APM_RPC.value: lambda: self.apm_rpc_url,
            AlertRedirectType.APM_TRACE.value: lambda: self.apm_trace_url,
        }

        redirect_types: list[str] = self.redirect_types
        if AlertRedirectType.APM_RPC.value in redirect_types and AlertRedirectType.QUERY.value in redirect_types:
            redirect_types.remove(AlertRedirectType.QUERY.value)

        redirect_infos: list[dict[str, Any]] = []
        for redirect_type in redirect_types:
            url_getter: Callable[[], str | None] = url_getters.get(redirect_type)
            if not url_getter:
                continue

            url: str | None = url_getter()
            if url:
                redirect_infos.append({"text": AlertRedirectType.from_value(redirect_type).label, "url": url})

        # 按 url_getters 顺序，最多同时给出三个场景的下钻链接。
        return redirect_infos[:3]

    def _build_redirect_short_url(self, redirect_type: str, check_in_redirect_types: bool = False) -> str | None:
        """
        构建告警重定向短链接

        通用的短链接生成方法，根据不同的重定向类型生成对应的短链接。
        短链接格式为 `{detail_url}&type={redirect_type}`，点击按钮后由 event_center_proxy 视图进行重定向，最终跳转到实际的目标页面。

        :param redirect_type: 重定向类型，对应 AlertRedirectType 枚举值
        :param check_in_redirect_types: 是否检查 redirect_type 在 self.redirect_types 中，默认 False
        :return: 短链接 URL，若无法生成则返回 None
        """
        # 如果需要检查重定向类型，且类型不在允许列表中，则返回 None
        if check_in_redirect_types and redirect_type not in self.redirect_types:
            return None

        url: str | None = self.detail_url
        if not url:
            return None

        return f"{url}&type={redirect_type}"

    @cached_property
    def apm_trace_url(self) -> str | None:
        """Tracing 检索跳转链接（短链接格式）"""
        return self._build_redirect_short_url(AlertRedirectType.APM_TRACE.value)

    @cached_property
    def apm_rpc_url(self) -> str | None:
        """调用分析跳转链接（短链接格式）"""
        return self._build_redirect_short_url(AlertRedirectType.APM_RPC.value)

    @cached_property
    def log_search_url(self) -> str | None:
        """
        日志检索跳转链接（短链接格式）

        通过短链接重定向到日志平台检索页面，时间范围为告警前 5 分钟(可配置) 到当前时刻，最多 1 小时。
        """
        return self._build_redirect_short_url(AlertRedirectType.LOG_SEARCH.value, check_in_redirect_types=True)

    @cached_property
    def event_explore_url(self) -> str | None:
        """事件检索跳转链接（短链接格式）"""
        return self._build_redirect_short_url(AlertRedirectType.EVENT_EXPLORE.value)

    @cached_property
    def query_url(self) -> str | None:
        """
        数据检索跳转链接（短链接格式）

        通过短链接重定向到数据检索页面，基于告警数据点的前后 1 小时时间范围。
        """
        return self._build_redirect_short_url(AlertRedirectType.QUERY.value, check_in_redirect_types=True)

    @cached_property
    def apm_query_url(self) -> str | None:
        """APM 自定义指标检索跳转链接（短链接格式）"""
        # TODO 后续 APM 实现自定义指标功能后，再更新为跳转到自定义指标检索页面
        return self._build_redirect_short_url(AlertRedirectType.QUERY.value)
