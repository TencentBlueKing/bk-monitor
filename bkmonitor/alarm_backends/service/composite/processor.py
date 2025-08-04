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
import time
from collections import defaultdict

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.core.cache.key import (
    ALERT_DETECT_KEY_LOCK,
    ALERT_DETECT_RESULT,
    ALERT_FIRST_HANDLE_RECORD,
    COMPOSITE_CHECK_RESULT,
    COMPOSITE_DETECT_RESULT,
    COMPOSITE_DIMENSION_KEY_LOCK,
)
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.item import gen_condition_matcher
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.fta_action.tasks import create_actions
from bkmonitor.documents import AlertLog
from bkmonitor.strategy.expression import AlertExpressionValue, parse_expression
from bkmonitor.utils.common_utils import count_md5
from constants.action import ActionSignal
from constants.alert import EventStatus
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("composite")


class CompositeProcessor:
    # 关联告警检测窗口大小（单位 s）
    COMPOSITE_CHECK_WINDOW_SIZE = 60 * 60

    def __init__(self, alert: Alert, alert_status: str = "", composite_strategy_ids: list = None, retry_times: int = 0):
        self.alert: Alert = alert
        self.alert_status = alert_status or self.alert.status
        # 此处仅做告警关联，不需要重复清洗数据
        self.event: Event = Event(data=alert.top_event, do_clean=False)
        self.strategy_ids = composite_strategy_ids
        self.strategies = []
        self.actions = []
        self.events = []
        self._strategy_cache = {}
        self.retry_times = retry_times

    def pull(self):
        if not self.strategy_ids:
            # 如果没有提供策略ID，则获取所有告警关联的策略
            if self.alert.strategy_id:
                strategy_ids_by_biz = StrategyCacheManager.get_fta_alert_strategy_ids(
                    strategy_id=self.alert.strategy_id
                )
            else:
                strategy_ids_by_biz = StrategyCacheManager.get_fta_alert_strategy_ids(alert_name=self.alert.alert_name)

            self.strategy_ids = strategy_ids_by_biz.get(str(self.alert.bk_biz_id), [])

        if self.strategy_ids:
            self.strategies = StrategyCacheManager.get_strategy_by_ids(self.strategy_ids)

    def add_action(self, strategy_id, signal, alert_ids, severity, dimensions):
        """
        即将推送到处理队列的数据
        """
        self.actions.append(
            {
                "strategy_id": strategy_id,
                "signal": signal,
                "alert_ids": alert_ids,
                "severity": severity,
                "dimensions": dimensions,
            }
        )

    def add_event(self, strategy, alert_by_alias, status, severity, dimensions, dimension_hash):
        """
        即将推送到事件队列的数据，用于二次告警生成
        """
        now_time = int(time.time())
        event_time = self.alert.update_time

        origin_dimensions = {d["key"]: d["value"] for d in dimensions}
        target_type, target, data_dimensions = MonitorEventAdapter.extract_target(strategy, origin_dimensions)

        # 对维度字段进行标准化，如 tags.xx -> xx, yy -> yy
        tags = []
        for dimension in dimensions:
            if dimension["key"] not in data_dimensions:
                continue
            if dimension["key"].startswith("tags."):
                key = dimension["key"][len("tags.") :]
            else:
                key = dimension["key"]
            tags.append(
                {
                    "key": key,
                    "value": dimension["value"],
                    "display_key": dimension["display_key"],
                    "display_value": dimension["display_value"],
                }
            )

        dedupe_keys = [f"tags.{tag['key']}" for tag in tags]

        if status == EventStatus.ABNORMAL:
            description = self.translate_expr(strategy, strategy["detects"][0]["expression"])
        else:
            description = _("当前不满足表达式，告警关闭")

        event = {
            "event_id": f"{dimension_hash}.{now_time}",
            "plugin_id": settings.MONITOR_EVENT_PLUGIN_ID,  # 来源固定为监控
            "strategy_id": strategy["id"],
            "alert_name": strategy["name"],
            "description": description,
            "severity": int(severity),
            "tags": tags,
            "target_type": target_type,
            "target": target,
            "status": status,
            "metric": [conf["metric_id"] for item in strategy["items"] for conf in item.get("query_configs", [])],
            "category": strategy["scenario"],
            "data_type": DataTypeLabel.ALERT,
            "dedupe_keys": dedupe_keys,
            "time": event_time,
            "bk_ingest_time": now_time,
            "bk_clean_time": now_time,
            "bk_biz_id": strategy["bk_biz_id"],
            "extra_info": {
                "origin_alarm": {
                    "data": {
                        "dimensions": origin_dimensions,
                        "value": 1 if status == EventStatus.ABNORMAL else 0,
                    }
                },
                "strategy": strategy,
            },
        }

        self.events.append(event)

    def push_events(self):
        if not self.events:
            return
        try:
            MonitorEventAdapter.push_to_kafka(self.events)
        except Exception as e:
            logger.exception("alert(%s) detect finished, but push events failed, reason: %s", self.alert.id, e)
            raise e
        else:
            logger.info("alert(%s) detect finished, push (%s) events to kafka", self.alert.id, len(self.events))

        for event in self.events:
            metrics.COMPOSITE_PUSH_EVENT_COUNT.labels(strategy_id=metrics.TOTAL_TAG, signal=event["status"]).inc()

        # 清空队列
        self.events = []

    def push_actions(self):
        if not self.actions:
            return

        # 对于满足条件的策略，推送信号到Action模块执行动作
        success_actions = 0
        qos_actions = 0
        current_count = 0
        for action in self.actions:
            # 限流计数器，监控的告警以策略ID，信号，告警级别作为维度
            try:
                is_qos, current_count = self.alert.qos_calc(action["signal"])
                logger.info(
                    "[composite send action] alert(%s) strategy(%s) signal(%s) severity(%s) ",
                    self.alert.id,
                    action["strategy_id"],
                    action["signal"],
                    action["severity"],
                )
                if not is_qos:
                    create_actions.delay(**action)
                    success_actions += 1
                else:
                    # 达到阈值之后，触发流控
                    logger.info(
                        "[action qos triggered] alert(%s) strategy(%s) signal(%s) severity(%s) qos_count: %s",
                        self.alert.id,
                        action["strategy_id"],
                        action["signal"],
                        action["severity"],
                        current_count,
                    )
                    qos_actions += 1
                    # 被QOS的，按照策略维度发送一份
                    # 被QOS的情况下，需要删除首次处理记录
                    first_handle_key = ALERT_FIRST_HANDLE_RECORD.get_key(
                        strategy_id=self.alert.strategy_id or 0, alert_id=self.alert.id, signal=action["signal"]
                    )
                    ALERT_FIRST_HANDLE_RECORD.client.delete(first_handle_key)

                    metrics.COMPOSITE_PUSH_ACTION_COUNT.labels(
                        strategy_id=action["strategy_id"], signal=action["signal"], is_qos="1", status="success"
                    ).inc()

                metrics.COMPOSITE_PUSH_ACTION_COUNT.labels(
                    strategy_id=metrics.TOTAL_TAG,
                    signal=action["signal"],
                    is_qos="1" if is_qos else "0",
                    status="success",
                ).inc()
            except Exception as e:
                logger.exception(
                    "[composite push action ERROR] alert(%s) strategy(%s) detail: %s",
                    self.alert.id,
                    action["strategy_id"],
                    e,
                )
                metrics.COMPOSITE_PUSH_ACTION_COUNT.labels(
                    strategy_id=metrics.TOTAL_TAG, is_qos="0", signal=action["signal"], status="failed"
                ).inc()
                continue
        if qos_actions:
            # 如果有被qos的事件， 进行日志记录
            qos_log = Alert.create_qos_log([self.alert.id], current_count, qos_actions)
            AlertLog.bulk_create([qos_log])

        # 清空队列
        self.actions = []
        return success_actions, qos_actions

    def get_strategy_name_by_id(self, strategy_id):
        if strategy_id in self._strategy_cache:
            return self._strategy_cache[strategy_id]

        strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if strategy:
            name = strategy["name"]
        else:
            name = _("策略({})").format(strategy_id)
        self._strategy_cache[strategy_id] = name
        return name

    def translate_expr(self, strategy, expr):
        alias_translation = {}
        try:
            for item in strategy["items"]:
                for query_config in item["query_configs"]:
                    if query_config["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR:
                        name = self.get_strategy_name_by_id(int(query_config["metric_id"].split(".")[-1]))
                    else:
                        name = query_config["metric_id"].split(".")[-1]
                    alias_translation[query_config["alias"]] = name
            expr_display = parse_expression(expr).translate(alias_translation)
        except Exception:
            expr_display = expr

        description = _("满足表达式 {expr}").format(expr=expr_display)

        return description

    def is_valid_datasource(self, query_config):
        """
        判断数据源类型是否满足条件
        """
        if (
            query_config["data_source_label"] == DataSourceLabel.BK_FTA
            and query_config["data_type_label"] == DataTypeLabel.ALERT
            and query_config["alert_name"] == self.alert.alert_name
        ):
            return True

        if (
            query_config["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR
            and query_config["data_type_label"] == DataTypeLabel.ALERT
            and query_config["bkmonitor_strategy_id"] == self.alert.strategy_id
        ):
            return True

        return False

    def match_query_config(self, query_config) -> bool:
        if not self.is_valid_datasource(query_config):
            return False

        agg_condition = query_config.get("agg_condition", [])

        condition = gen_condition_matcher(agg_condition)
        return condition.is_match(self.event.to_flatten_dict())

    @classmethod
    def cal_public_dimensions(cls, strategy):
        public_dimensions = None

        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                # 计算出公共维度
                dimensions = {dimension for dimension in query_config.get("agg_dimension", []) if dimension}
                if public_dimensions is None:
                    public_dimensions = dimensions
                else:
                    public_dimensions &= dimensions

        return list(public_dimensions or set())

    def cal_match_query_configs(self, strategy):
        matched_configs = {}
        unmatched_configs = {}
        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                query_config_md5 = count_md5(query_config)
                if self.match_query_config(query_config):
                    matched_configs[query_config_md5] = query_config
                else:
                    unmatched_configs[query_config_md5] = query_config
        return matched_configs, unmatched_configs

    def get_alert_by_alias(self, strategy, dimension_hash, matched_configs, unmatched_configs):
        """
        获取每个query_config对应的告警
        例如 {"A": Alert(x), "B": Alert(y)}
        """
        check_start_time = int(time.time()) - self.COMPOSITE_CHECK_WINDOW_SIZE

        # 每个别名所关联的告警对象
        alert_by_alias = {}

        # 1. 对于匹配的item，直接注入到表达式上下文
        for query_config_id, config in matched_configs.items():
            cache_key = COMPOSITE_CHECK_RESULT.get_key(
                strategy_id=strategy["id"], dimension_hash=dimension_hash, query_config_id=query_config_id
            )
            # 清理过期的 item
            COMPOSITE_CHECK_RESULT.client.zremrangebyscore(cache_key, 0, check_start_time - COMPOSITE_CHECK_RESULT.ttl)
            if self.alert_status == EventStatus.ABNORMAL:
                # 如果是异常告警，则一定是触发的
                COMPOSITE_CHECK_RESULT.client.zadd(cache_key, {self.alert.id: self.alert.update_time})
                check_result = AlertExpressionValue.ABNORMAL
            else:
                # 如果不是异常告警，则还要看检测结果缓存中是否还有其他异常告警
                # 当没有其他告警时，当前配置才会被认为是不满足，否则就仍为异常
                COMPOSITE_CHECK_RESULT.client.zrem(cache_key, self.alert.id)
                abnormal_count = COMPOSITE_CHECK_RESULT.client.zcount(cache_key, check_start_time, "+inf")
                if abnormal_count:
                    check_result = AlertExpressionValue.ABNORMAL
                else:
                    check_result = AlertExpressionValue.NORMAL

            alert_by_alias[config["alias"]] = check_result

            # 更新过期时间
            COMPOSITE_CHECK_RESULT.expire(
                strategy_id=strategy["id"], dimension_hash=dimension_hash, query_config_id=query_config_id
            )

        # 2. 没匹配到的item，需要到缓存中查询，获取计算结果后再注入到表达式上下文
        query_config_id_list = []
        for query_config_id, config in unmatched_configs.items():
            cache_key = COMPOSITE_CHECK_RESULT.get_key(
                strategy_id=strategy["id"], dimension_hash=dimension_hash, query_config_id=query_config_id
            )
            abnormal_count = COMPOSITE_CHECK_RESULT.client.zcount(cache_key, check_start_time, "+inf")
            if abnormal_count:
                check_result = AlertExpressionValue.ABNORMAL
            else:
                check_result = AlertExpressionValue.NORMAL

            alert_by_alias[config["alias"]] = check_result

            query_config_id_list.append(query_config_id)

        return alert_by_alias

    def do_detect(self, strategy, dimension_hash, alert_by_alias):
        """
        策略检测逻辑
        """
        # 1. 根据每个告警的状态，生成一个 Dict Context
        expression_context = defaultdict(lambda: AlertExpressionValue.NO_DATA)
        for alias, expression_value in alert_by_alias.items():
            expression_context[alias] = expression_value

        # 2. 从 detect 中获取条件表达式，对条件表达式进行初始化
        detect_result = defaultdict(list)
        algorithm_connector = {}
        for detect in strategy["detects"]:
            try:
                compiled_expression = parse_expression(detect["expression"])
                # 将上下文丢进去进行计算，得到计算结果
                expression_result = compiled_expression.eval(expression_context)
            except Exception as e:
                logger.exception(
                    "strategy(%s) dimension(%s) calculate expression failed: %s, detect config: %s",
                    strategy["id"],
                    dimension_hash,
                    e,
                    detect,
                )
                expression_result = AlertExpressionValue.NO_DATA
            algorithm_connector[int(detect["level"])] = detect.get("connector") or "and"
            detect_result[int(detect["level"])].append(expression_result)

        detect_result_by_level = {}
        # 同级别算法连接符(and/or)
        for level, results in detect_result.items():
            match_count = len([r for r in results if r == AlertExpressionValue.ABNORMAL])
            if algorithm_connector[level] != "or" and len(results) == match_count:
                # 如果是and，且所有同级别条件都满足，则该级别成立
                level_result = True
            elif match_count >= 1:
                # 如果是or，只要其中一个条件满足，则该级别成立
                level_result = True
            else:
                # 否则，条件不成立
                level_result = False
            detect_result_by_level[str(level)] = level_result

        logger.debug(
            "strategy(%s) dimension(%s) detect result: %s", strategy["id"], dimension_hash, detect_result_by_level
        )

        # 3. 从缓存中拿到上一次的计算结果
        try:
            cached_detect_result = json.loads(
                COMPOSITE_DETECT_RESULT.client.get(
                    COMPOSITE_DETECT_RESULT.get_key(strategy_id=strategy["id"], dimension_hash=dimension_hash)
                )
            )
        except Exception:
            cached_detect_result = {}

        # 4. 与当前计算结果进行比较
        abnormal_level = None
        is_closed = False
        for level, result in sorted(detect_result_by_level.items(), key=lambda d: int(d[0])):
            if not result and cached_detect_result.get(level):
                # 当前结果为正常，但缓存结果为异常，则被判定为恢复
                is_closed = True
                abnormal_level = level
            elif result and not cached_detect_result.get(level):
                # 当上一次检测结果是非异常，且本次检测结果为异常，则满足了触发条件
                is_closed = False
                abnormal_level = level
                break

        return abnormal_level, is_closed, detect_result_by_level

    def process_composite_strategy(self, strategy):
        """
        关联告警：对单个策略进行检测
        :return: 二元组，触发配置(detect), 关联的告警ID列表
        """
        if not strategy["detects"]:
            # 没有检测算法，直接退出
            return

        matched_configs, unmatched_configs = self.cal_match_query_configs(strategy)

        # 如果任何 id 都不匹配，那么直接退出
        if not matched_configs:
            return

        # 计算出公共维度
        public_dimensions = self.cal_public_dimensions(strategy)

        # 从事件中提取出所需的维度的KV结构
        dimension_values = {key: self.event.get_field(key) for key in public_dimensions}

        # 计算维度MD5
        dimension_hash = count_md5(dimension_values)

        # 给当前维度MD5加锁
        try:
            with service_lock(COMPOSITE_DIMENSION_KEY_LOCK, strategy_id=strategy["id"], dimension_hash=dimension_hash):
                # 1. 加锁成功

                # 2. 获取每个query_config对应的告警
                alert_by_alias = self.get_alert_by_alias(strategy, dimension_hash, matched_configs, unmatched_configs)

                # 3. 进行关联告警检测
                abnormal_level, is_closed, detect_result = self.do_detect(strategy, dimension_hash, alert_by_alias)

                if not abnormal_level:
                    logger.debug(
                        "strategy(%s) dimension(%s) detect finished, do nothing", strategy["id"], dimension_values
                    )
                    return

                logger.info(
                    "strategy(%s) dimension(%s) detect finished, level(%s) detected, alert(%s), closed(%s)",
                    strategy["id"],
                    dimension_values,
                    abnormal_level,
                    self.alert.id,
                    is_closed,
                )

                # 尝试翻译一波维度
                dimension_translations = {d["key"]: d for d in self.alert.dimensions}
                dimensions = []
                for key, value in dimension_values.items():
                    if key in dimension_translations and dimension_translations[key]["value"] == value:
                        display_key = dimension_translations[key].get("display_key", key)
                        display_value = dimension_translations[key].get("display_value", value)
                    else:
                        display_key = key
                        display_value = value

                    dimensions.append(
                        {
                            "key": key,
                            "value": value,
                            "display_key": display_key,
                            "display_value": display_value,
                        }
                    )

                self.add_event(
                    strategy=strategy,
                    status=EventStatus.CLOSED if is_closed else EventStatus.ABNORMAL,
                    alert_by_alias=alert_by_alias,
                    severity=abnormal_level,
                    dimensions=dimensions,
                    dimension_hash=dimension_hash,
                )
                event = self.events[-1]
                self.push_events()

                # 将本次结果写入缓存
                COMPOSITE_DETECT_RESULT.client.set(
                    COMPOSITE_DETECT_RESULT.get_key(strategy_id=strategy["id"], dimension_hash=dimension_hash),
                    json.dumps(detect_result),
                    COMPOSITE_DETECT_RESULT.ttl,
                )
                return event

        except LockError:
            # 加锁失败，重新发布任务
            logger.info(
                "[get service lock fail] composite strategy->({}), dimension->({}). will process later".format(
                    strategy["id"], dimension_values
                )
            )
            from alarm_backends.service.composite.tasks import (
                check_action_and_composite,
            )

            self.retry_times += 2
            check_action_and_composite.apply_async(
                kwargs={
                    "alert_key": self.alert.key,
                    "alert_status": self.alert_status,
                    "composite_strategy_ids": [strategy["id"]],
                    "retry_times": self.retry_times,
                },
                countdown=1,
            )
        except Exception as error:
            # 其他未知异常情况下，需要先捕获异常，避免影响其他策略
            logger.exception("strategy(%s) detect error, %s", strategy["id"], str(error))

    def clear_composite_detect_cache(self):
        """
        清理关联告警检测的缓存
        """
        if not self.is_composite_strategy():
            return
        # 如果是关联告警，则还需要清除关联告警检测缓存
        composite_dimension_hash = str(self.alert.top_event["event_id"]).split(".")[0]
        if not composite_dimension_hash:
            return

        COMPOSITE_DETECT_RESULT.client.delete(
            COMPOSITE_DETECT_RESULT.get_key(
                strategy_id=self.alert.strategy_id,
                dimension_hash=composite_dimension_hash,
            )
        )

        key_pattern = COMPOSITE_CHECK_RESULT.get_key(
            strategy_id=self.alert.strategy_id, dimension_hash=composite_dimension_hash, query_config_id="*"
        )
        keys = COMPOSITE_CHECK_RESULT.client.keys(key_pattern)
        if keys:
            COMPOSITE_CHECK_RESULT.client.delete(*keys)

    def process_single_strategy(self):
        """
        单告警策略（监控特有）
        """
        strategy_id = self.alert.strategy_id
        if not (strategy_id or self.alert.get_extra_info("matched_rule_info")):
            # 没有策略也没有适配规则，直接返回
            return

        try:
            with service_lock(ALERT_DETECT_KEY_LOCK, alert_id=self.alert.id):
                cache_key = ALERT_DETECT_RESULT.get_key(alert_id=self.alert.id)
                cached_result = ALERT_DETECT_RESULT.client.get(cache_key)

                signal = None

                if cached_result and not self.alert_status == EventStatus.ABNORMAL:
                    # 当前有异常，但告警已经是非异常状态，需要发信号
                    # 注意：无数据告警不需要发送恢复和关闭信号
                    if self.alert_status == EventStatus.RECOVERED:
                        signal = ActionSignal.RECOVERED
                    else:
                        signal = ActionSignal.CLOSED
                elif not cached_result and self.alert_status == EventStatus.ABNORMAL:
                    # 当前无异常，但告警是异常状态，需要发信号
                    if self.alert.is_no_data():
                        # 无数据告警
                        signal = ActionSignal.NO_DATA
                    else:
                        signal = ActionSignal.ABNORMAL
                elif cached_result and self.alert_status == EventStatus.ABNORMAL and self.alert.is_ack_signal:
                    # 如果缓存中存在告警，且当前的告警已经确认并没有发送通知，则属于告警确认的情况，需要发一个确认任务信号
                    signal = ActionSignal.ACK
                elif (
                    cached_result
                    and self.alert_status == EventStatus.ABNORMAL
                    and self.alert.severity < int(cached_result)
                ):
                    # 如果缓存中存在告警，且当前的告警级别比缓存中的级别要高，则属于告警升级的情况，需要发一个异常信号
                    signal = ActionSignal.ABNORMAL
                elif cached_result and self.alert_status == EventStatus.ABNORMAL:
                    # 如果当前缓存已经存在，但是并没有处理过的情况下， 需要重新发送执行信号
                    check_signal = ActionSignal.NO_DATA if self.alert.is_no_data() else ActionSignal.ABNORMAL
                    is_send_handle_signal = ALERT_FIRST_HANDLE_RECORD.client.get(
                        ALERT_FIRST_HANDLE_RECORD.get_key(
                            strategy_id=strategy_id, alert_id=self.alert.id, signal=check_signal
                        )
                    )
                    if not (self.alert.is_handled or is_send_handle_signal):
                        # 如果没有处理过或者已经发送了处理信号，直接忽略
                        if int(time.time()) - self.alert.create_time >= settings.QOS_DROP_ACTION_WINDOW:
                            # 这类没有处理过的数据，一般有可能是因为QOS引起的，所以可以延迟一点再发送, 否则相同的周期内，会有重复的自增记录
                            signal = check_signal

                action = None
                if signal:
                    # 推送动作信号
                    if signal != ActionSignal.ABNORMAL and not strategy_id:
                        # 如果是第三方分派的情况下，忽略非异常信号的通知
                        logger.info(
                            "[composite ignore] alert(%s) signal(%s) source(%s), no strategy_id",
                            signal,
                            self.alert.id,
                            self.alert.top_event.get("plugin_id", ""),
                        )
                    else:
                        first_handle_key = ALERT_FIRST_HANDLE_RECORD.get_key(
                            strategy_id=self.alert.strategy_id or 0, alert_id=self.alert.id, signal=signal
                        )
                        if ALERT_FIRST_HANDLE_RECORD.client.set(
                            first_handle_key, 1, nx=True, ex=ALERT_FIRST_HANDLE_RECORD.ttl
                        ):
                            # 只有第一次设置成功，才可以进行消息推送
                            # todo 优化
                            self.add_action(
                                strategy_id=strategy_id,
                                signal=signal,
                                alert_ids=[self.alert.id],
                                severity=self.alert.severity,
                                dimensions=self.alert.dimensions,
                            )
                            # 这里没必要再执行一次，因为已经设置成功了
                            # ALERT_FIRST_HANDLE_RECORD.client.expire(first_handle_key, ALERT_FIRST_HANDLE_RECORD.ttl)
                            action = self.actions[-1]
                        self.push_actions()

                # 推送动作成功后，将本次结果写入缓存
                if self.alert_status == EventStatus.ABNORMAL:
                    ALERT_DETECT_RESULT.client.set(cache_key, self.alert.severity, ALERT_DETECT_RESULT.ttl)
                else:
                    ALERT_DETECT_RESULT.client.delete(cache_key)
                    self.clear_composite_detect_cache()

                return action

        except LockError:
            # 加锁失败，重新发布任务
            from alarm_backends.service.composite.tasks import (
                check_action_and_composite,
            )

            self.retry_times += 2
            check_action_and_composite.apply_async(
                kwargs={
                    "alert_key": self.alert.key,
                    "alert_status": self.alert_status,
                    "retry_times": self.retry_times,
                },
                countdown=1,
            )

    def is_composite_strategy(self):
        """
        检查是否为关联告警策略
        """
        strategy = self.alert.get_extra_info("strategy")
        if not strategy:
            return False
        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                if query_config["data_type_label"] == DataTypeLabel.ALERT:
                    return True
        return False

    def process(self):
        self.process_single_strategy()

        # 1. 如果告警本身就是由关联告警策略产生的，则不再进行关联检测
        # 2. 如果告警是无数据告警，则不参与关联检测
        if not self.is_composite_strategy() and not self.alert.is_no_data():
            #  关联告警逻辑处理
            self.pull()
            for strategy in self.strategies:
                in_alarm_time, message = Strategy(strategy["id"], strategy).in_alarm_time()
                if not in_alarm_time:
                    logger.info("[composite] strategy(%s) not in alarm time: %s, skipped", strategy["id"], message)
                    continue
                self.process_composite_strategy(strategy)
