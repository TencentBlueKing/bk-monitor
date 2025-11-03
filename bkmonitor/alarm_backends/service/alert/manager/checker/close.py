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
import logging
import time

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.constants import CONST_MINUTES
from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.cmdb import HostManager, ServiceInstanceManager
from alarm_backends.core.cache.key import (
    ALERT_DEDUPE_CONTENT_KEY,
    LAST_CHECKPOINTS_CACHE_KEY,
    NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY,
)
from alarm_backends.core.control.record_parser import EventIDParser
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.priority import PriorityChecker
from alarm_backends.service.alert.manager.checker.base import BaseChecker
from api.cmdb.define import TopoNode
from bkmonitor.documents import AlertLog
from bkmonitor.models import AlgorithmModel
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.time_tools import hms_string
from constants.action import AssignMode
from constants.alert import EventStatus, EventTargetType
from constants.data_source import DataTypeLabel

logger = logging.getLogger("alert.manager")


def get_agg_condition_md5(agg_condition):
    # 查询条件变更判定，仅关注核心影响数据查询的条件字段
    key_list = ["key", "value", "method", "condition"]
    target_condition = []
    for agg in agg_condition:
        target_condition.append({key: agg[key] for key in key_list if key in agg})
    if target_condition:
        # 第一个条件的condition， 默认都是AND， 因此直接去掉，不参与变更判定
        target_condition[0].pop("condition", None)
    return count_md5(target_condition)


class CloseStatusChecker(BaseChecker):
    """
    事件关闭判断
    """

    DEFAULT_CHECK_WINDOW_UNIT = 60

    def check(self, alert: Alert):
        if not alert.is_abnormal():
            # 告警已经是非异常状态了，无需检查
            return

        # 检查告警是否已经过期
        if self.check_event_expired(alert):
            return

        if not alert.strategy_id:
            # 没有策略ID的，说明不是监控策略，不使用于当前检测
            return

        latest_strategy_obj = Strategy(alert.strategy_id)

        latest_strategy = latest_strategy_obj.config

        # 检查策略是否被删除
        if not latest_strategy:
            logger.info(
                "[close 处理结果] (closed) alert(%s), strategy(%s) 策略已被停用或删除，告警关闭",
                alert.id,
                alert.strategy_id,
            )
            self.close(alert, _("策略已被停用或删除，告警关闭"))
            return True

        # 检查是否在策略的生效时间内，特地给2分钟的冗余
        in_alarm_time, message = latest_strategy_obj.in_alarm_time()
        if not in_alarm_time:
            logger.info(
                "[close 处理结果] (closed) alert(%s), strategy(%s) %s, 告警关闭",
                alert.id,
                alert.strategy_id,
                message,
            )
            self.close(alert, _("{}，告警关闭").format(message))
            return True

        latest_item = latest_strategy["items"][0]

        # 检查策略是否被修改
        if self.check_strategy_changed(alert, latest_strategy):
            return True

        # 检查当前告警的目标实例是否还在策略的监控范围内
        if self.check_target_not_included(alert, latest_strategy_obj.items):
            return True

        # 检查是否为无数据上报（仅限时序数据）
        if self.check_no_data(alert, latest_item, latest_strategy):
            return True

        # 检查优先级
        if self.check_priority(alert, latest_strategy):
            return True

        return False

    def check_strategy_changed(self, alert: Alert, latest_strategy):
        """
        检查策略是否被修改
        """
        latest_item = latest_strategy["items"][0]

        origin_strategy = alert.get_extra_info("strategy")
        origin_item = origin_strategy["items"][0]

        # 1. 检查metric_id是否被修改
        origin_metric_ids = [query["metric_id"] for query in latest_item["query_configs"]]
        metric_ids = [query["metric_id"] for query in origin_item["query_configs"]]
        if origin_metric_ids != metric_ids:
            logger.info(
                "[close 处理结果] (closed) alert({}), strategy({}), 策略监控项已被修改，告警关闭".format(
                    alert.id, alert.strategy_id
                )
            )
            self.close(alert, _("策略监控项已被修改，告警关闭"))
            return True

        # 2. 检查监控维度是否被修改
        for origin_query, latest_query in zip(origin_item["query_configs"], latest_item["query_configs"]):
            latest_dimensions = origin_query.get("agg_dimension", [])
            origin_dimensions = latest_query.get("agg_dimension", [])
            if set(latest_dimensions) != set(origin_dimensions):
                logger.info(
                    "[close 处理结果] (closed) alert({}), strategy({}), 策略监控维度已被修改，告警关闭".format(
                        alert.id,
                        alert.strategy_id,
                    )
                )
                self.close(alert, _("策略监控维度已被修改，告警关闭"))
                return True

        # 3. 检查当前告警级别是否被删除
        if not alert.is_no_data():
            latest_levels = [str(detect["level"]) for detect in latest_strategy["detects"]]
            if (
                not self.check_skip_close_by_algorithm(latest_item)
                and alert.severity_source != AssignMode.BY_RULE
                and str(alert.severity) not in latest_levels
            ):
                logger.info(
                    "[close 处理结果] (closed) alert({}), strategy({}), "
                    "告警级别对应的检测算法已被删除，告警关闭".format(
                        alert.id,
                        alert.strategy_id,
                    )
                )
                self.close(alert, _("告警级别对应的检测算法已被删除，告警关闭"))
                return True
        else:
            # 如果是无数据告警，还需要判断 agg_condition 是否发生了改变，一旦改变了就关闭
            for origin_query, latest_query in zip(origin_item["query_configs"], latest_item["query_configs"]):
                origin_condition = origin_query.get("agg_condition", [])
                latest_condition = latest_query.get("agg_condition", [])
                origin_condition_md5 = get_agg_condition_md5(origin_condition)
                latest_condition_md5 = get_agg_condition_md5(latest_condition)
                if origin_condition_md5 != latest_condition_md5:
                    logger.info(
                        "[close 处理结果] (closed) alert({}), strategy({}), 策略过滤条件已被修改，告警关闭".format(
                            alert.id,
                            alert.strategy_id,
                        )
                    )
                    self.close(alert, _("策略过滤条件已被修改，告警关闭"))
                    return True

            # 4. 当前的是无数据告警，且无数据告警配置被关闭，则直接关闭告警
            if not latest_item["no_data_config"]["is_enabled"]:
                logger.info(
                    "[close 处理结果] (closed) alert({}), strategy({}), 无数据告警设置被关闭，告警关闭".format(
                        alert.id, alert.strategy_id
                    )
                )
                self.close(alert, _("无数据告警设置被关闭，告警关闭"))
                return True

        return False

    def check_event_expired(self, alert: Alert):
        # 获取当前正在发生的事件ID
        current_alert_data = ALERT_DEDUPE_CONTENT_KEY.client.get(
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=alert.strategy_id or 0, dedupe_md5=alert.dedupe_md5)
        )
        try:
            current_alert = json.loads(current_alert_data)
            current_alert = Alert(current_alert)
        except Exception:
            # 如果从缓存中获取不到告警，表示当前告警应该为最新的告警信息，默认不做关闭
            return False

        if current_alert and current_alert.id != alert.id:
            # 如果从缓存中获取到了数据信息，并且缓存中的告警ID与当前告警ID不一致，则认为是存在更新的告警
            # 如果正在发生的事件ID与当前事件ID不一致，则说明事件已经过期，直接关闭
            logger.info(
                "[close 处理结果] (closed) alert({}), strategy({}) 当前维度存在更新的告警事件({})，告警已失效".format(
                    alert.id, alert.strategy_id, current_alert.id
                )
            )
            self.close(alert, _("当前维度存在更新的告警事件({})，告警已失效").format(current_alert.id))
            return True
        # 如果一致的话，表示是同一个告警，则认为告警在持续
        return False

    def check_no_data(self, alert: Alert, latest_item, latest_strategy):
        """
        检查是否为无数据上报（仅限时序数据）
        """
        if alert.is_no_data():
            # 如果是无数据告警，则忽略
            return self.check_no_data_for_nodata_alert(alert)

        # 是否为时序类告警
        data_type_label = latest_item["query_configs"][0]["data_type_label"]
        if data_type_label not in (DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG):
            # 如果是非时序类告警，则不检查
            return False

        parser = EventIDParser(alert.top_event["event_id"])

        # 获取当前维度最新上报时间
        # TODO: 自愈告警会存在告警级别漂移的情况，需要进行特殊处理
        last_check_timestamp = LAST_CHECKPOINTS_CACHE_KEY.client.hget(
            LAST_CHECKPOINTS_CACHE_KEY.get_key(
                strategy_id=parser.strategy_id,
                item_id=parser.item_id,
            ),
            LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5=parser.dimensions_md5,
                level=parser.level,
            ),
        )
        last_check_timestamp = int(last_check_timestamp) if last_check_timestamp else 0

        now_timestamp = int(time.time())
        trigger_config = Strategy.get_trigger_configs(latest_strategy)[str(parser.level)]
        trigger_window_size = max(trigger_config["check_window_size"], settings.EVENT_NO_DATA_TOLERANCE_WINDOW_SIZE)
        query_configs = latest_item["query_configs"]

        window_unit = Strategy.get_check_window_unit(latest_item, self.DEFAULT_CHECK_WINDOW_UNIT)

        # TODO：智能异常检测，目前只支持单指标
        if query_configs[0].get("intelligent_detect", {}) and not query_configs[0]["intelligent_detect"].get(
            "use_sdk", False
        ):
            # 智能异常检测在计算平台会经过几层dataflow，会有一定的周期延时，所以这里需要再加上这个延时窗口
            trigger_window_size = trigger_window_size + settings.BK_DATA_INTELLIGENT_DETECT_DELAY_WINDOW

        if data_type_label == DataTypeLabel.LOG:
            recovery_config = Strategy.get_recovery_configs(latest_strategy)[str(parser.level)]
            recovery_window_size = recovery_config["check_window_size"]
            nodata_tolerance_time = max((trigger_window_size + recovery_window_size) * window_unit, 5 * CONST_MINUTES)
        else:
            nodata_tolerance_time = max(trigger_window_size * window_unit, 30 * CONST_MINUTES)

        if int(last_check_timestamp) + nodata_tolerance_time < now_timestamp:
            # 如果最近上报时间距离当前时间超过了一个触发窗口的大小，则认为无数据上报，告警关闭
            self.close(alert, _("在恢复检测周期内无数据上报，告警已失效"))
            logger.info(
                "[close 处理结果] (closed) alert({}), strategy({}), last_check_timestamp({}), now_timestamp({}),"
                "在恢复检测周期内无数据上报，进行事件关闭".format(
                    alert.id, alert.strategy_id, last_check_timestamp, now_timestamp
                )
            )
            return True
        return False

    def check_no_data_for_nodata_alert(self, alert):
        """
        检查无数据告警是否已经关闭
        :param alert:
        :return:
        """
        latest_time = alert.latest_time
        current_time = int(time.time())
        if current_time - latest_time > settings.NO_DATA_ALERT_EXPIRED_TIMEDELTA:
            self.close(
                alert,
                _("在恢复检测周期内，已经有 %s 没有产生无数据关联事件，告警已失效")
                % hms_string(settings.NO_DATA_ALERT_EXPIRED_TIMEDELTA),
            )
            return True
        return False

    def check_target_not_included(self, alert: Alert, latest_items):
        need_check_items = []
        for item in latest_items:
            if item.target_condition_obj:
                # 存在target, 才进行判断
                need_check_items.append(item)

        if not need_check_items:
            # 如果都没有设置target,直接忽略
            return False

        target_dimensions = {}
        if alert.top_event["target_type"] == EventTargetType.HOST:
            # CMDBEnricher 的 enrich_host 方法 会对event 设置ip字段，但如果主机缓存缺失，则会导致丢失ip字段
            ip = target_dimensions["ip"] = alert.top_event.get("ip", "")
            bk_cloud_id = target_dimensions["bk_cloud_id"] = alert.top_event.get("bk_cloud_id", "")
            host = None
            if ip and bk_cloud_id != "":
                host = HostManager.get(ip, bk_cloud_id)
            if not host:
                # 如果主机在缓存中不存在，则直接恢复告警
                # 需要考虑一个问题，如何判断缓存未刷新的情况
                logger.info(
                    "[close 处理结果] (closed) alert({}), strategy({}), CMDB 未查询到告警目标主机 ({}|{}) 的信息，主机可能已被删除，告警关闭".format(
                        alert.id, alert.strategy_id, ip, bk_cloud_id
                    )
                )
                self.close(
                    alert,
                    _("CMDB 未查询到告警目标主机 ({}|{}) 的信息，主机可能已被删除，告警关闭").format(ip, bk_cloud_id),
                )
                return True

            target_dimensions["bk_host_id"] = host.bk_host_id
            topo_link = list(host.topo_link.values())

        elif alert.top_event["target_type"] == EventTargetType.SERVICE:
            target_dimensions["bk_target_service_instance_id"] = bk_service_instance_id = alert.top_event[
                "bk_service_instance_id"
            ]
            service_instance = ServiceInstanceManager.get(target_dimensions["bk_target_service_instance_id"])

            if not service_instance:
                # 如果服务实例在缓存中不存在，则直接恢复告警
                logger.info(
                    "[close 处理结果] (closed) alert({}), strategy({}), "
                    "CMDB 未查询到告警目标服务实例 ({}) 的信息，服务实例可能已被删除，告警关闭".format(
                        alert.id, alert.strategy_id, bk_service_instance_id
                    )
                )
                self.close(
                    alert,
                    _("CMDB 未查询到告警目标服务实例 ({}) 的信息，服务实例可能已被删除，告警关闭").format(
                        bk_service_instance_id
                    ),
                )
                return True

            topo_link = list(service_instance.topo_link.values())

        elif alert.top_event["target_type"] == EventTargetType.TOPO:
            bk_obj_id, bk_inst_id = alert.top_event["target"].split("|")
            topo_link = [[TopoNode(bk_obj_id=bk_obj_id, bk_inst_id=bk_inst_id)]]

        else:
            # 如果都不是以上的类型，则跳过检测
            return False

        target_dimensions["bk_topo_node"] = {node.id for nodes in topo_link for node in nodes}
        for item in need_check_items:
            if not item.target_condition_obj.is_match(target_dimensions):
                logger.info(
                    "[close 处理结果] (closed) alert({}), strategy({}), 告警目标实例已不在监控目标范围内，告警关闭."
                    "当前TOPO: {}".format(
                        alert.id,
                        alert.strategy_id,
                        target_dimensions,
                    )
                )
                self.close(alert, _("告警目标实例已不在监控目标范围内，告警关闭"))
                return True
        return False

    def check_priority(self, alert: Alert, latest_strategy):
        """
        检查告警优先级
        """
        priority = latest_strategy.get("priority")
        priority_group_key = latest_strategy.get("priority_group_key")
        if priority is None or not priority_group_key or not alert.top_event:
            return False

        dimension_md5 = alert.top_event["event_id"].split(".")[0]
        checker = PriorityChecker(priority_group_key=priority_group_key)
        result = checker.get_priority_by_dimensions(dimension_md5)
        if not result:
            return False

        latest_priority, latest_timestamp = result.split(":")

        interval = 60
        for item in latest_strategy["items"]:
            for query_config in item["query_configs"]:
                if "agg_interval" in query_config and query_config["agg_interval"] > interval:
                    interval = query_config["agg_interval"]

        if float(latest_timestamp) + interval * 5 < time.time() or int(latest_priority) <= priority:
            return False

        self.close(alert, _("存在更高优先级的告警，告警关闭"))
        return True

    @classmethod
    def close(cls, alert: Alert, description):
        """
        事件关闭
        """
        alert.set_end_status(status=EventStatus.CLOSED, op_type=AlertLog.OpType.CLOSE, description=description)

        # 无数据告警，清理最后检测异常点记录
        if alert.is_no_data():
            parser = EventIDParser(alert.top_event["event_id"])
            NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.client.hdel(
                NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_key(),
                NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_field(
                    strategy_id=parser.strategy_id, item_id=parser.item_id, dimensions_md5=parser.dimensions_md5
                ),
            )

    def check_skip_close_by_algorithm(self, strategy_item) -> bool:
        """检查是否需要根据算法来跳过关闭告警的逻辑.

        :param strategy_item: 策略配置
        :return: 是否需要跳过关闭检测
        """
        if (
            len(strategy_item["algorithms"]) > 0
            and strategy_item["algorithms"][0]["type"] == AlgorithmModel.AlgorithmChoices.HostAnomalyDetection
        ):
            return True

        return False
