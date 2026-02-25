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
import json
import logging
import urllib.parse
from collections import defaultdict
from json import JSONDecodeError
from urllib import parse

from django.conf import settings
from django.db.models import Max
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.models import AnomalyRecord
from bkmonitor.utils import time_tools
from bkmonitor.utils.template import NoticeRowRenderer
from constants.alert import CMDB_TARGET_DIMENSIONS
from constants.apm import ApmAlertHelper
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.unit import load_unit

from . import BaseContextObject

logger = logging.getLogger("fta_action.run")


class DefaultContent(BaseContextObject):
    """
    通知内容对象
    """

    Fields = (
        "level",
        "time",
        "begin_time",
        "duration",
        "target_type",
        "data_source",
        "content",
        "biz",
        "target",
        "dimension",
        "detail",
        "current_value",
        "related_info",
        "appointees",
        "assign_reason",
        "ack_operators",
        "ack_reason",
        "sms_forced_related_info",
        "business_name",
        "assign_detail",
        "anomaly_dimensions",
        "recommended_metrics",
        "receivers",
    )

    def __getattribute__(self, item):
        """
        取值时自动获取相应通知类型的值
        """
        if item in object.__getattribute__(self, "Fields"):
            content_type = self.parent.notice_way
            if self.parent.notice_way in settings.MD_SUPPORTED_NOTICE_WAYS:
                # 所有支持markdown语法的通知方式，默认用markdown格式
                content_type = "markdown"
            if hasattr(self, f"{item}_{content_type}"):
                value = object.__getattribute__(self, f"{item}_{content_type}")
            else:
                value = super().__getattribute__(item)

            if value is None:
                return ""
            else:
                return NoticeRowRenderer.format(content_type, self.Labels[item][content_type], value)

        return super().__getattribute__(item)

    # 告警级别
    @cached_property
    def level(self):
        return None

    # 最近一次时间
    @cached_property
    def time(self):
        return time_tools.utc2localtime(self.parent.alert.latest_time).strftime(settings.DATETIME_FORMAT)

    # 首次异常时间
    @cached_property
    def begin_time(self):
        return self.parent.alarm.begin_time.strftime(settings.DATETIME_FORMAT)

    # 持续时间
    @cached_property
    def duration(self):
        return None

    # 监控目标类型
    @cached_property
    def target_type(self):
        return None

    # 监控数据来源
    @cached_property
    def data_source(self):
        return None

    # 告警内容
    @cached_property
    def content(self):
        return self.parent.alarm.description

    # 所属业务
    @cached_property
    def biz(self):
        return self.parent.target.business.display_name

    # 监控目标
    @property
    def target(self):
        return self.parent.alarm.target_string

    # 维度
    @cached_property
    def dimension(self):
        if not self.parent.alarm.display_dimensions:
            return None

        return self.parent.alarm.dimension_string

    # 告警详情
    @cached_property
    def detail(self):
        return self.parent.alarm.detail_url

    # 当前值
    @cached_property
    def current_value(self):
        return None

    # 关联信息
    @cached_property
    def related_info(self):
        return self.parent.alarm.related_info

    # 短信关联信息
    @cached_property
    def sms_forced_related_info(self):
        return self.parent.alarm.related_info

    # 被分派人
    @cached_property
    def appointees(self):
        """
        负责人信息
        """
        if self.parent.alarm.appointees:
            return ",".join(self.parent.alarm.appointees)
        return None

    @cached_property
    def receivers(self):
        """
        告警接收人信息

        优先级：merged_notice_receivers > notice_receiver > alarm.receivers
        - merged_notice_receivers: 合并通知后的所有接收人（与实际发送一致）
        - notice_receiver: 单个接收人或列表
        - alarm.receivers: 从 alert.assignee 获取（向后兼容）
        """
        # 优先使用合并后的接收人
        if hasattr(self.parent, "merged_notice_receivers") and self.parent.merged_notice_receivers:
            merged_receivers = self.parent.merged_notice_receivers
            if isinstance(merged_receivers, list) and merged_receivers:
                return ",".join(merged_receivers)
            elif merged_receivers:
                return merged_receivers if isinstance(merged_receivers, str) else str(merged_receivers)

        # 使用 context 中的 notice_receiver
        if hasattr(self.parent, "notice_receiver") and self.parent.notice_receiver:
            notice_receiver = self.parent.notice_receiver
            if isinstance(notice_receiver, list):
                return ",".join(notice_receiver) if notice_receiver else ""
            elif notice_receiver:
                return notice_receiver if isinstance(notice_receiver, str) else str(notice_receiver)

        # fallback 到 alarm.receivers
        if self.parent.alarm.receivers:
            return ",".join(self.parent.alarm.receivers)
        return None

    # 分派原因
    @cached_property
    def assign_reason(self):
        return getattr(self.parent, "assign_reason", None)

    @cached_property
    def ack_reason(self):
        return ",".join(self.parent.alarm.ack_reason)

    @cached_property
    def ack_reason_markdown(self):
        reasons = ["\\n> " + reason for reason in self.parent.alarm.ack_reason]
        reasons = "".join(reasons) + "\\n"
        return reasons

    @cached_property
    def ack_operators(self):
        return ",".join(set(self.parent.alarm.ack_operators))

    # markdown
    @cached_property
    def detail_markdown(self):
        return None

    @cached_property
    def biz_markdown(self):
        return self.parent.target.business.display_name

    @cached_property
    def target_markdown(self):
        alerts = self.parent.alerts
        monitor_host = settings.BK_MONITOR_HOST
        target_dict = defaultdict(dict)
        for alert in alerts:
            display_dimensions = []
            filter_data = []
            if getattr(alert.event, "category", None) == "kubernetes":
                dimensions = {d["key"].replace("tags.", ""): d for d in alert.common_dimensions}
                namespace = cluster = container = pod = ""
                dashboard = ""
                for key in ["bcs_cluster_id", "cluster", "cluster_id"]:
                    if key not in dimensions:
                        continue
                    cluster = dimensions[key]["value"]
                    dashboard = "cluster"
                    filter_data.append({"bcs_cluster_id": cluster})

                node = dimensions.get("node", {}).get("value", "")
                if node:
                    # 为node的时候，直接忽略其他分支的判断
                    dashboard = "node"
                    filter_data.append({"keyword": node})
                else:
                    namespace = dimensions.get("namespace", {}).get("value", "")
                    for key in ["pod", "pod_name"]:
                        if key not in dimensions:
                            continue
                        pod = dimensions[key]["value"]

                    if namespace or pod:
                        dashboard = "pod"
                        if namespace:
                            filter_data.append({"namespace": namespace})

                    for key in ["container", "container_name"]:
                        if key not in dimensions:
                            continue
                        container = dimensions[key]["value"]
                        dashboard = "container"
                        filter_data.append({"name": container})
                        filter_data.append({"pod_name": pod})
                if dashboard == "pod" and pod:
                    filter_data.append({"name": pod})
                if dashboard:
                    query_data = parse.quote(
                        parse.quote(json.dumps({"page": 0, "selectorSearch": filter_data, "filterDict": {}}))
                    )
                    route_path = (
                        f"#/k8s?dashboardId={dashboard}&sceneId=kubernetes&sceneType=overview&queryData={query_data}"
                    )
                    route_path = base64.b64encode(route_path.encode("utf8")).decode("utf8")
                    link = urllib.parse.urljoin(
                        monitor_host, f"route/?bizId={self.parent.business.bk_biz_id}&route_path={route_path}"
                    )
                    value = "|".join([item for item in [cluster, node, namespace, pod, container] if item])
                    display_dimensions.append({"value": value, "link": link})
            elif getattr(alert.event, "category", None) == "apm" and alert.strategy:
                dimensions: dict[str, str | None] = {
                    d["key"].replace("tags.", ""): d["value"] for d in alert.common_dimensions
                }
                apm_target: dict[str, str | None] = ApmAlertHelper.get_target(alert.strategy, dimensions)
                app_name, service_name = apm_target.get("app_name"), apm_target.get("service_name")
                if not app_name:
                    continue
                if service_name:
                    display_dimensions.append(
                        {
                            "value": _(f"**APM 服务 <{app_name} | {service_name}>**"),
                            "link": urllib.parse.urljoin(
                                monitor_host,
                                f"?bizId={self.parent.business.bk_biz_id}#/apm/service"
                                f"?filter-service_name={service_name}&filter-app_name={app_name}",
                            ),
                        }
                    )
                else:
                    display_dimensions.append(
                        {
                            "value": _(f"**APM 应用<{app_name}>**"),
                            "link": urllib.parse.urljoin(
                                monitor_host, f"?bizId={self.parent.business.bk_biz_id}#/apm/home?app_name={app_name}"
                            ),
                        }
                    )
            else:
                bk_cloud_id = getattr(alert.event, "bk_cloud_id", 0)
                dimensions = {d["key"]: d for d in alert.target_dimensions}
                for key in CMDB_TARGET_DIMENSIONS:
                    if key not in dimensions or key in ["bk_cloud_id", "bk_target_cloud_id"]:
                        # 云区域ID暂时去掉
                        continue
                    value = dimensions[key]["value"]
                    display_value = dimensions[key].get("display_value") or value
                    link = ""
                    if key in ["ip", "bk_target_ip"]:
                        route_path = base64.b64encode(f"#/performance/detail/{value}-{bk_cloud_id}".encode()).decode(
                            "utf8"
                        )
                        link = urllib.parse.urljoin(
                            monitor_host, f"route/?bizId={self.parent.business.bk_biz_id}&route_path={route_path}"
                        )
                    if display_value:
                        display_dimensions.append({"value": display_value, "link": link})
            for dimension in display_dimensions:
                if dimension["value"] in target_dict:
                    target_dict[dimension["value"]]["count"] += 1
                    continue
                target_dict[dimension["value"]] = dimension
                target_dict[dimension["value"]]["count"] = 1
        targets = []
        for value, item in target_dict.items():
            if item["link"]:
                targets.append(
                    f"[{value}({item['count']})]({item['link']})" if item["count"] > 1 else f"[{value}]({item['link']})"
                )
            else:
                # 需要保证targets里都是字符串
                targets.append(f"{value}({item['count']})" if item["count"] > 1 else str(value))

        return ", ".join(targets) if targets else None

    @cached_property
    def assign_detail(self):
        return self.parent.alarm.assign_detail

    @cached_property
    def assign_detail_markdown(self):
        if not self.parent.alarm.assign_detail:
            return None
        return _("[查看详情]({})").format(self.parent.alarm.assign_detail)

    @cached_property
    def recommended_metrics(self):
        return self.parent.alarm.recommended_metrics

    @cached_property
    def anomaly_dimensions(self):
        return self.parent.alarm.anomaly_dimensions

    @cached_property
    def remarks(self):
        alert_id = self.parent.alert.id
        bk_biz_id = self.parent.business.bk_biz_id
        try:
            remarks = list(
                filter(lambda e: e.get("is_match"), api.monitor.get_experience(bk_biz_id=bk_biz_id, alert_id=alert_id))
            )
        except BKAPIError:
            remarks = ""

        if not remarks:
            return ""
        remark_collection = defaultdict(list)
        for remark in remarks:
            if remark["type"] == "metric":
                # 基于指标的告警经验默认最低优先级命中: 0
                remark_collection[0].append(remark["description"])
                continue
            score = len(remark["conditions"])
            remark_collection[score].append(remark["description"])
        return " | ".join(remark_collection[max(remark_collection)])


class DimensionCollectContent(DefaultContent):
    """
    同维度汇总告警内容
    """

    Labels = {
        "begin_time": defaultdict(lambda: _lazy("首次异常")),
        "time": defaultdict(lambda: _lazy("最近异常")),
        "level": defaultdict(lambda: _lazy("级别"), {"mail": _lazy("告警级别")}),
        "duration": defaultdict(lambda: _lazy("持续时间")),
        "target_type": defaultdict(lambda: _lazy("告警对象")),
        "data_source": defaultdict(lambda: _lazy("数据来源")),
        "content": defaultdict(lambda: _lazy("内容"), {"mail": _lazy("告警内容")}),
        "biz": defaultdict(lambda: _lazy("所属空间")),
        "target": defaultdict(lambda: _lazy("目标"), {"mail": _lazy("告警目标")}),
        "dimension": defaultdict(lambda: _lazy("维度"), {"mail": _lazy("告警维度")}),
        "detail": defaultdict(lambda: _lazy("详情"), {"sms": _lazy("告警ID")}),
        "current_value": defaultdict(lambda: _lazy("当前值")),
        "related_info": defaultdict(lambda: _lazy("关联信息")),
        "appointees": defaultdict(lambda: _lazy("负责人")),
        "assign_reason": defaultdict(lambda: _lazy("分派原因")),
        "ack_reason": defaultdict(lambda: _lazy("确认原因")),
        "ack_operators": defaultdict(lambda: _lazy("确认人")),
        "sms_forced_related_info": defaultdict(lambda: _lazy("关联信息")),
        "assign_detail": defaultdict(lambda: _lazy("分派详情")),
        "anomaly_dimensions": defaultdict(lambda: _lazy("维度下钻")),
        "recommended_metrics": defaultdict(lambda: _lazy("关联指标")),
        "receivers": defaultdict(lambda: _lazy("告警接收人")),
        "remarks": defaultdict(lambda: _lazy("备注")),
    }

    # 短信
    @cached_property
    def time_sms(self):
        return None

    @cached_property
    def begin_time_sms(self):
        return None

    @cached_property
    def detail_sms(self):
        return self.parent.alert.id

    @cached_property
    def related_info_sms(self):
        return None

    @cached_property
    def sms_forced_related_info_sms(self):
        if len(self.parent.alarm.related_info) > 300:
            # 默认不能大于300个字符，当大于300的时候，仅保留300字符
            return f"{self.parent.alarm.related_info[:297]}..."
        return self.parent.alarm.related_info

    # 邮件
    @cached_property
    def duration_mail(self):
        return self.parent.alarm.duration_string

    @cached_property
    def target_type_mail(self):
        return self.parent.alarm.target_type_name

    @cached_property
    def data_source_mail(self):
        return self.parent.alarm.data_source_name

    @cached_property
    def content_mail(self):
        return self.parent.alarm.description

    @cached_property
    def biz_mail(self):
        return self.parent.target.business.display_name

    @cached_property
    def target_mail(self):
        if not self.parent.alarm.display_targets:
            return None

        target_message = ",".join(self.parent.alarm.display_targets)
        return target_message

    @cached_property
    def detail_mail(self):
        return None

    @cached_property
    def current_value_mail(self):
        if self.parent.alarm.current_value is None:
            return None
        try:
            unit = load_unit(self.parent.strategy.items[0].unit)
            value, suffix = unit.fn.auto_convert(self.parent.alarm.current_value, decimal=settings.POINT_PRECISION)
            return f"{value}{suffix}"
        except BaseException as error:
            # 出现异常的时候，直接返回当前值
            logger.info("get alarm current value of email error %s", str(error))
            return self.parent.alarm.current_value

    @cached_property
    def level_mail(self):
        return self.parent.alert.severity_display

    # markdown格式的维度信息
    @cached_property
    def dimension_markdown(self):
        if not self.parent.alarm.dimension_string_list:
            return ""

        dimension_string_list: list[str] = []
        for dimension_str in self.parent.alarm.dimension_string_list:
            k, v = dimension_str.split(": ", 1)
            dimension_string_list.append(f"\\n> **{k}**: {v}")
        dimension_str = "".join(dimension_string_list) + "\\n"
        return dimension_str

    @cached_property
    def related_info_markdown(self):
        topo_related_info = self.parent.alarm.topo_related_info
        log_related_info = self.parent.alarm.log_related_info
        if not log_related_info:
            return topo_related_info
        try:
            log_related_info = json.loads(topo_related_info)
            bklog_link = log_related_info.pop("bklog_link", "")
            log_related_info = json.dumps(log_related_info)
            log_related_info += f"[日志详情]({bklog_link})"
        except JSONDecodeError as error:
            # 如果json loads不成功， 忽略
            logger.debug("json loads alarm log_related_info failed %s", str(error))
        log_related_info = "\\n> " + log_related_info + "\\n"
        return topo_related_info + log_related_info

    @cached_property
    def assign_detail(self):
        if not self.parent.alarm.assign_detail:
            return None


class MultiStrategyCollectContent(DefaultContent):
    """
    多维度多策略汇总告警内容
    """

    Labels = {
        "begin_time": defaultdict(lambda: _lazy("首次异常")),
        "time": defaultdict(lambda: _lazy("最近异常"), {"mail": _lazy("时间范围")}),
        "level": defaultdict(lambda: _lazy("级别"), {"mail": _lazy("告警级别")}),
        "duration": defaultdict(lambda: _lazy("持续时间")),
        "target_type": defaultdict(lambda: _lazy("告警对象")),
        "data_source": defaultdict(lambda: _lazy("数据来源")),
        "content": defaultdict(lambda: _lazy("内容"), {"sms": _lazy("代表")}),
        "biz": defaultdict(lambda: _lazy("告警业务")),
        "target": defaultdict(lambda: _lazy("目标")),
        "dimension": defaultdict(lambda: _lazy("维度")),
        "detail": defaultdict(lambda: _lazy("详情"), {"sms": _lazy("告警ID"), "markdown": ""}),
        "current_value": defaultdict(lambda: _lazy("当前值")),
        "related_info": defaultdict(lambda: _lazy("关联信息")),
        "appointees": defaultdict(lambda: _lazy("负责人")),
        "assign_reason": defaultdict(lambda: _lazy("分派原因")),
        "ack_reason": defaultdict(lambda: _lazy("确认原因")),
        "ack_operators": defaultdict(lambda: _lazy("确认人")),
        "sms_forced_related_info": defaultdict(lambda: _lazy("关联信息")),
        "assign_detail": defaultdict(lambda: _lazy("分派详情")),
        "anomaly_dimensions": defaultdict(lambda: _lazy("维度下钻")),
        "recommended_metrics": defaultdict(lambda: _lazy("关联指标")),
        "receivers": defaultdict(lambda: _lazy("告警接收人")),
        "remarks": defaultdict(lambda: _lazy("备注")),
    }

    # 微信
    @cached_property
    def detail_weixin(self):
        return None

    # 短信
    @cached_property
    def time_sms(self):
        return None

    @cached_property
    def begin_time_sms(self):
        return None

    @cached_property
    def related_info_sms(self):
        return None

    @cached_property
    def detail_sms(self):
        return self.parent.alert.id

    @cached_property
    def content_sms(self):
        if self.parent.alarm.end_description:
            # 如果已经结束，发送结束的描述信息
            return self.parent.alarm.end_description

        duration_message = ""
        if self.parent.alarm.duration_string:
            duration_message = _("已持续{},")

        return _("[{}]{} {}告警,{}{}").format(
            self.parent.event.level_name,
            self.strategy.strategy_name,
            time_tools.utc2localtime(self.parent.alert.latest_time).time().strftime("%H:%M"),
            duration_message,
            self.parent.alert.event.description,
        )

    # 邮件
    @cached_property
    def level_mail(self):
        return self.parent.alert.severity_display

    @cached_property
    def time_mail(self):
        # TODO 这里如何适配
        event_ids = {event_action["event_id"] for event_action in self.parent.event_actions}

        # 获取事件最近异常点的时间
        latest_anomaly_records = (
            AnomalyRecord.objects.filter(event_id__in=event_ids).values("event_id").annotate(max_id=Max("id"))
        )
        latest_anomaly_records = AnomalyRecord.objects.filter(
            id__in=[record["max_id"] for record in latest_anomaly_records]
        ).values("source_time")
        source_times = [record["source_time"] for record in latest_anomaly_records]

        # 统计最大最小时间
        max_time = time_tools.localtime(max(source_times))
        min_time = time_tools.localtime(min(source_times))

        time_range = f"{min_time.strftime(settings.DATETIME_FORMAT)} ~ {max_time.strftime(settings.DATETIME_FORMAT)}"
        return time_range

    @cached_property
    def begin_time_mail(self):
        return None

    @cached_property
    def biz_mail(self):
        return self.parent.target.business.display_name

    @cached_property
    def data_source_mail(self):
        return self.parent.alarm.data_source_name

    @cached_property
    def content_mail(self):
        return None

    @cached_property
    def dimension_mail(self):
        return None

    @cached_property
    def detail_mail(self):
        return None

    @cached_property
    def target_mail(self):
        return None

    @cached_property
    def related_info(self):
        return None

    @cached_property
    def sms_forced_related_info(self):
        return None
