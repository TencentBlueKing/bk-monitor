"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import bisect
import logging
import time

from django.conf import settings
from django.utils.translation import gettext as _
from redis.exceptions import WatchError

from alarm_backends.constants import CONST_MINUTES
from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.key import (
    CHECK_RESULT_CACHE_KEY,
    LAST_CHECKPOINTS_CACHE_KEY,
    NEW_SERIES_ACTIVE_KEY,
    NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY,
)
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.record_parser import EventIDParser
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.detect_result import ANOMALY_LABEL
from alarm_backends.core.storage.redis_cluster import routed_client
from alarm_backends.service.alert.manager.checker.base import BaseChecker
from alarm_backends.service.alert.manager.checker.utils import (
    is_auto_level_intelligent_detect,
    resolve_new_series_lifecycle_state,
)
from bkmonitor.data_source import CustomEventDataSource
from bkmonitor.documents import AlertLog
from bkmonitor.models import AlgorithmModel
from constants.alert import EventStatus
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.unit import load_unit

logger = logging.getLogger("alert.manager")


class RecoverStatusChecker(BaseChecker):
    """
    事件恢复判断
    """

    DEFAULT_CHECK_WINDOW_UNIT = 60
    DEFAULT_CHECK_WINDOW_SIZE = 5
    DEFAULT_TRIGGER_COUNT = 0
    DEFAULT_STATUS_SETTER = "recovery"
    NEW_SERIES_MISSING = "missing"
    NEW_SERIES_ACTIVE = "active"
    NEW_SERIES_EXPIRED = "expired"
    NEW_SERIES_CLAIM_RETRIES = 3

    def check(self, alert: Alert):
        if not alert.is_abnormal():
            # 告警已经是非异常状态了，无需检查
            return

        if not alert.strategy_id:
            return

        if alert.is_no_data():
            self.check_no_data(alert)
            return

        strategy = StrategyCacheManager.get_strategy_by_id(int(alert.strategy_id))
        if not strategy:
            strategy = alert.get_extra_info("strategy")

        if self.check_new_series_lifecycle(alert, strategy):
            return

        if self.check_trigger_result(alert, strategy):
            return

        if self.check_custom_event_recovery(alert, strategy):
            return

    def check_new_series_lifecycle(self, alert, strategy):
        """持续模式使用独立活跃态保持告警，并按 detect_range 结束生命周期。"""
        lifecycle = resolve_new_series_lifecycle_state(alert, strategy)
        if lifecycle is None:
            return False
        observed_at = int(time.time())
        try:
            lifecycle_state = self.claim_new_series_expiration(
                lifecycle.active_key,
                lifecycle.fingerprint,
                expire_before=observed_at - lifecycle.detect_range,
                claimed_key=lifecycle.claimed_key,
                observed_at=observed_at,
                soft_ttl=lifecycle.soft_ttl,
                max_series=lifecycle.max_series,
            )
        except Exception as e:  # noqa  活跃态不可读时宁可保持告警，避免 Redis 抖动造成错误恢复。
            logger.exception(
                "[new_series lifecycle] alert(%s) strategy(%s) active state read failed, keep alert: %s",
                alert.id,
                alert.strategy_id,
                e,
            )
            return True

        if lifecycle_state == self.NEW_SERIES_MISSING:
            # 兼容存量告警、配置切换或续期写失败：没有专用状态时继续走既有恢复逻辑。
            return False

        if lifecycle_state == self.NEW_SERIES_ACTIVE:
            return True

        status_setter = self.get_recovery_status_setter(alert, strategy)
        self.recover(
            alert,
            _("新维度值在检测周期内未再次出现，告警已{handle}"),
            status_setter=status_setter,
            preserve_new_series_lifecycle=True,
        )
        logger.info(
            "[new_series lifecycle] alert(%s) strategy(%s) observation window expired, status_setter(%s)",
            alert.id,
            alert.strategy_id,
            status_setter,
        )
        return True

    @classmethod
    def claim_new_series_expiration(
        cls,
        active_key,
        fingerprint,
        expire_before,
        *,
        claimed_key,
        observed_at,
        soft_ttl,
        max_series,
    ):
        """原子认领到期 member 并留下有界 tombstone，供下一次有效出现启动新生命周期。"""
        proxy = NEW_SERIES_ACTIVE_KEY.client
        with routed_client(proxy, active_key) as client:
            for attempt in range(cls.NEW_SERIES_CLAIM_RETRIES):
                pipe = client.pipeline(transaction=True)
                try:
                    pipe.watch(active_key, claimed_key)
                    active_score = pipe.zscore(active_key, fingerprint)
                    if active_score is None:
                        claimed_score = pipe.zscore(claimed_key, fingerprint)
                        pipe.unwatch()
                        if claimed_score is not None and int(float(claimed_score)) > observed_at - soft_ttl:
                            return cls.NEW_SERIES_EXPIRED
                        return cls.NEW_SERIES_MISSING
                    if int(float(active_score)) >= expire_before:
                        pipe.unwatch()
                        return cls.NEW_SERIES_ACTIVE

                    claimed_score = pipe.zscore(claimed_key, fingerprint)
                    claimed_count = int(pipe.zcard(claimed_key))
                    stale_count = int(pipe.zcount(claimed_key, "-inf", observed_at - soft_ttl))
                    live_count = max(0, claimed_count - stale_count)
                    marker_exists = claimed_score is not None and int(float(claimed_score)) > observed_at - soft_ttl
                    capacity = max(0, int(max_series))
                    trim_excess = max(0, live_count + (0 if marker_exists else 1) - capacity)

                    pipe.multi()
                    pipe.zrem(active_key, fingerprint)
                    pipe.zremrangebyscore(claimed_key, "-inf", observed_at - soft_ttl)
                    pipe.zadd(claimed_key, {fingerprint: observed_at})
                    if trim_excess:
                        pipe.zremrangebyrank(claimed_key, 0, trim_excess - 1)
                    pipe.expire(claimed_key, soft_ttl)
                    removed = pipe.execute()[0]
                    if removed:
                        return cls.NEW_SERIES_EXPIRED
                except WatchError:
                    if attempt + 1 == cls.NEW_SERIES_CLAIM_RETRIES:
                        raise
                finally:
                    pipe.reset()
        raise RuntimeError(f"failed to claim expired NewSeries member after retries: {active_key}")

    @classmethod
    def get_recovery_status_setter(cls, alert, strategy):
        try:
            recovery_configs = Strategy.get_recovery_configs(strategy)
            for level in map(str, [alert.event_severity, alert.severity]):
                if level in recovery_configs:
                    status_setter = recovery_configs[level]["status_setter"]
                    break
            else:
                status_setter = recovery_configs[str(alert.event_severity)]["status_setter"]
            return status_setter.split("-", 1)[0]
        except (ValueError, TypeError, IndexError, KeyError):
            return cls.DEFAULT_STATUS_SETTER

    def check_no_data(self, alert: Alert):
        """
        检查无数据恢复
        """
        if not alert.is_no_data():
            # 如果不是无数据告警，则不检测
            return False
        parser = EventIDParser(alert.top_event["event_id"])
        no_data_checkpoint = NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.client.hget(
            NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_key(),
            NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_field(
                strategy_id=parser.strategy_id, item_id=parser.item_id, dimensions_md5=parser.dimensions_md5
            ),
        )
        if no_data_checkpoint:
            # 检测缓存还在，说明无数据告警仍在产生
            return False
        self.recover(alert, _("当前维度检测到新的上报数据，无数据告警已恢复"))
        return True

    def recover_by_nodata(self, alert, status_setter):
        self.recover(alert, _("在恢复检测周期内无数据上报，告警已{handle}"), status_setter=status_setter)
        check_result = ("do_close" if status_setter == "close" else "do_recover",)
        logger.info(
            "[recover 处理结果] ({}) alert({}), strategy({}) 在恢复检测周期内无数据上报，进行事件{}".format(
                check_result, alert.id, alert.strategy_id, _("关闭") if status_setter == "close" else _("恢复")
            )
        )

    def check_trigger_result(self, alert, strategy):
        """
        检测触发结果是否满足条件
        """
        item = strategy["items"][0]
        query_config = item["query_configs"][0]

        is_composite_strategy = query_config["data_type_label"] == DataTypeLabel.ALERT

        if is_composite_strategy:
            # 关联告警不在此处判断
            return

        parser = EventIDParser(alert.top_event["event_id"])

        # 是否为事件类型告警
        is_event_type = query_config["data_type_label"] == DataTypeLabel.EVENT
        is_time_series = query_config["data_type_label"] in (DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG)

        window_unit = Strategy.get_check_window_unit(item, self.DEFAULT_CHECK_WINDOW_UNIT)
        recovery_with_nodata = False
        try:
            recovery_configs_map = Strategy.get_recovery_configs(strategy)
            recovery_configs = self.select_level_config(
                recovery_configs_map, item, [alert.event_severity, alert.severity]
            )
            recovery_window_size = recovery_configs["check_window_size"]
            status_setter = recovery_configs["status_setter"]
            # 新增无数据恢复配置: "recovery-nodata"
            if "-" in status_setter:
                status_setter, case = status_setter.split("-")
                recovery_with_nodata = case == "nodata"
        except (ValueError, TypeError, IndexError, KeyError):
            logger.error(f"event{alert.id} has no status_setter in recovery_configs.\norigin strategy is {strategy}")
            recovery_window_size = self.DEFAULT_CHECK_WINDOW_SIZE
            status_setter = self.DEFAULT_STATUS_SETTER

        recovery_window_offset = window_unit * recovery_window_size

        try:
            trigger_config = self.select_level_config(
                Strategy.get_trigger_configs(strategy), item, [alert.event_severity]
            )
            trigger_window_size = trigger_config["check_window_size"]
            trigger_count = trigger_config["trigger_count"]
        except (ValueError, TypeError, IndexError, KeyError):
            logger.exception(
                "strategy({}), level({}) trigger_config does not exist, using default trigger config".format(
                    strategy["id"], alert.event_severity
                )
            )
            # 如果获取trigger失败，则将触发窗口设置为与恢复窗口一样大小
            trigger_window_size = recovery_window_size
            trigger_count = self.DEFAULT_TRIGGER_COUNT

        trigger_window_offset = window_unit * trigger_window_size - 1

        now_ts = int(time.time())

        if is_event_type:
            last_check_timestamp = now_ts
            # 如果是自定义事件类型告警，因为周期较长的数据点检测时间向前对齐，所以需要使用当前时间减去一个周期窗口去判断， 避免提前恢复
            if query_config["data_source_label"] != DataSourceLabel.BK_MONITOR_COLLECTOR:
                last_check_timestamp -= window_unit
        else:
            # 如果是时序或日志类型告警，则使用最后一次上报时间判断
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

            if not last_check_timestamp:
                # key 已经过期，超时恢复
                self.recover_by_nodata(alert, status_setter)
                return True

            last_check_timestamp = int(last_check_timestamp)
            if recovery_with_nodata:
                # 配置了无数据恢复， 则判断当前无数据时长是否符合恢复窗口
                if now_ts > last_check_timestamp + recovery_window_offset + trigger_window_offset + window_unit:
                    # 超过恢复+触发窗口，无数据，进行恢复/关闭
                    # key 已经过期，超时恢复
                    self.recover_by_nodata(alert, status_setter)
                    return True

            # 无数据判定的最大周期通过对比告警触发周期和最大无数据容忍周期，默认取最大周期
            nodata_tolerance_size = max(trigger_window_size, settings.EVENT_NO_DATA_TOLERANCE_WINDOW_SIZE)

            # 无数据判定的最大周期时间，容忍时间小于30分钟，默认取最近30分钟的数据，大于30分钟，则按照周期时间处理
            nodata_tolerance_time = max(nodata_tolerance_size * window_unit, 30 * CONST_MINUTES)

            last_check_timestamp = max(
                last_check_timestamp,
                now_ts - nodata_tolerance_time,
            )

        check_result, latest_normal_record = self.check_result_cache(
            alert=alert,
            last_check_timestamp=last_check_timestamp,
            recovery_window_offset=recovery_window_offset,
            recovery_window_size=recovery_window_size,
            trigger_window_offset=trigger_window_offset,
            trigger_count=trigger_count,
            window_unit=window_unit,
            is_time_series=is_time_series,
        )
        if check_result:
            # 满足恢复条件，开始恢复
            self.recover(
                alert,
                _("连续 {} 个周期不满足触发条件，告警已{{handle}}").format(recovery_window_size),
                status_setter=status_setter,
                latest_normal_record=latest_normal_record,
                strategy_item=item,
            )
            logger.info(
                "[{}] alert({}), strategy({}) 连续 {} 个周期内不满足触发条件，进行事件{}".format(
                    "do_close" if status_setter == "close" else "do_recover",
                    alert.id,
                    alert.strategy_id,
                    recovery_window_size,
                    "关闭" if status_setter == "close" else "恢复",
                )
            )
            return True

        logger.info(
            f"[no_recover] alert({alert.id}), strategy({alert.strategy_id}) 在恢复检测周期内仍满足触发条件，不进行恢复"
        )
        return False

    def check_custom_event_recovery(self, alert: Alert, strategy):
        """
        根据event_type维度判断自定义事件是恢复还是异常
        """

        # 是否是自定义事件上报
        query_config = strategy["items"][0]["query_configs"][0]

        is_custom_report = (
            query_config["data_type_label"] == DataTypeLabel.EVENT
            and query_config["data_source_label"] == DataSourceLabel.CUSTOM
        )

        if not is_custom_report:
            return False

        datasource = CustomEventDataSource.init_by_query_config(query_config, bk_biz_id=alert.bk_biz_id)

        es_data, recovery_total = datasource.add_recovery_filter(datasource).query_log(
            start_time=int(alert.begin_time * 1000)
        )

        # 存在恢复event则恢复
        if recovery_total > 0:
            self.recover(alert, _("接收到自定义恢复事件，告警已恢复"))
            return True

        return False

    @classmethod
    def check_result_cache(
        cls,
        alert: Alert,
        last_check_timestamp,
        recovery_window_offset,
        recovery_window_size,
        trigger_window_offset,
        trigger_count,
        window_unit,
        is_time_series,
    ):
        """
        通过查询检测结果缓存判断事件是否达到恢复条件
        """
        # 如果有 last_check_timestamp 就需要判断是否满足触发条件
        parser = EventIDParser(alert.top_event["event_id"])
        latest_normal_record = (0, None)

        check_cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=parser.strategy_id,
            item_id=parser.item_id,
            dimensions_md5=parser.dimensions_md5,
            level=parser.level,
        )
        # 时间范围为：最后一次上报时间 - 触发窗口偏移 - 恢复窗口偏移
        min_check_timestamp = last_check_timestamp - recovery_window_offset - trigger_window_offset
        check_results = CHECK_RESULT_CACHE_KEY.client.zrangebyscore(
            name=check_cache_key, min=min_check_timestamp, max=last_check_timestamp, withscores=True
        )

        # 时序型无数据走关闭逻辑
        if not check_results and is_time_series:
            logger.info("[ignore recover] alert(%s) strategy(%s) no check result", alert.id, alert.strategy_id)
            return False, latest_normal_record

        # 取出包含异常数的个数，并排序
        check_result_timestamps = [int(score) for label, score in check_results]
        check_result_timestamps.sort()
        anomaly_timestamps = []

        for label, score in check_results:
            if label.endswith(ANOMALY_LABEL):
                # 如果是异常的数据结构，记录异常之后直接做下一个数据的检测
                anomaly_timestamps.append(int(score))
                continue
            score, normal_value = label.split("|")
            try:
                # 对获取的数据点进行格式化，int > float > error
                normal_value = int(normal_value)
            except ValueError:
                try:
                    normal_value = float(normal_value)
                except ValueError:
                    # 当前数据非整形或者浮点型的情况，可能有异常，用于后续流水日志，不影响大局
                    pass
            if int(score) > latest_normal_record[0]:
                # 记录时间戳最新的一个为最近正常数据点
                latest_normal_record = (int(score), normal_value)
        anomaly_timestamps.sort()

        logger.debug(
            f"[check_result_cache] alert({alert.id}), strategy({alert.strategy_id}), start_time({min_check_timestamp}), end_time({last_check_timestamp}) "
            f"anomaly_timestamps({anomaly_timestamps})"
        )

        # 按照监控周期移动触发判断窗口
        current_check_end_time = last_check_timestamp
        current_check_start_time = current_check_end_time - trigger_window_offset
        for i in range(recovery_window_size):
            # 使用二分查找找到起止时间对应的下标
            start_index = bisect.bisect_left(anomaly_timestamps, current_check_start_time)
            end_index = bisect.bisect_right(anomaly_timestamps, current_check_end_time)
            anomaly_count = end_index - start_index

            if anomaly_count >= trigger_count:
                # 当某个窗口的异常数量大于等于触发个数，即满足了触发条件，不恢复
                if i == 0 and alert.is_recovering():
                    # 日志不国际化
                    logger.info(
                        "[recover aborted] alert(%s) strategy(%s) 最近一个检测周期内仍满足触发条件，告警处理抑制解除",
                        alert.id,
                        alert.strategy_id,
                    )
                    alert.update_extra_info("is_recovering", False)
                    if alert.get_extra_info("ignore_unshield_notice"):
                        # 如果恢复周期内抑制了 解除屏蔽告警，解除抑制后, 需要重新发出，保证告警不丢失
                        # 这里删除抑制标记， 并重新设置 发送屏蔽告警 标记
                        alert.extra_info.pop("ignore_unshield_notice", False)
                        alert.update_extra_info("need_unshield_notice", True)
                    alert.add_log(
                        AlertLog.OpType.ABORT_RECOVER,
                        description=_("最近一个检测周期内仍满足触发条件，告警处理抑制解除"),
                    )
                return False, latest_normal_record
            if i == 0 and not alert.is_recovering():
                # 最近一次检测窗口没有异常，表示正在恢复周期内
                logger.info("[start recovering] alert(%s) strategy(%s)", alert.id, alert.strategy_id)
                # is_recovering 表示当前未恢复的告警开启恢复周期
                alert.update_extra_info("is_recovering", True)
                alert.add_log(
                    AlertLog.OpType.RECOVERING,
                    description=_("最近一个检测周期内不满足触发条件，当前告警处于恢复期内，告警处理将被抑制"),
                )

            # 未满足条件，则移动窗口，继续判断
            current_check_start_time -= window_unit
            current_check_end_time -= window_unit
        return True, latest_normal_record

    @classmethod
    def recover(
        cls,
        alert,
        description,
        status_setter="recovery",
        latest_normal_record: tuple = None,
        strategy_item: dict = None,
        preserve_new_series_lifecycle: bool = False,
    ):
        """
        事件恢复
        """
        if status_setter == "close":
            status = EventStatus.CLOSED
            op_type = AlertLog.OpType.CLOSE
            handle = _("关闭")
        else:
            status = EventStatus.RECOVERED
            op_type = AlertLog.OpType.RECOVER
            handle = _("恢复")
        description = description.format(handle=handle)
        if latest_normal_record:
            record_value_display = cls.get_value_display(alert, latest_normal_record[1])
            # 如果是AIOPS多指标的智能异常检测，则不展示当前值(is_anomaly)，后续考虑从接口获取当前恢复时所以监控的多个指标的值
            if record_value_display and not (strategy_item and cls.check_is_multi_indicator_strategy(strategy_item)):
                description = _("{description}，当前值为{record_value_display}").format(
                    description=description, record_value_display=record_value_display
                )
            alert.update_extra_info("recovery_value", latest_normal_record[1])
        alert.set_end_status(
            status=status,
            op_type=op_type,
            description=description,
            preserve_new_series_lifecycle=preserve_new_series_lifecycle,
        )

    @classmethod
    def get_value_display(cls, alert, value):
        strategy = Strategy(alert.strategy_id, alert.get_extra_info("strategy"))
        if not strategy.config or value is None:
            return value

        try:
            unit = load_unit(strategy.items[0].unit)
            value, suffix = unit.fn.auto_convert(value, decimal=settings.POINT_PRECISION)
            return f"{value}{suffix}"
        except Exception:
            return value

    @classmethod
    def check_is_multi_indicator_strategy(cls, strategy_item) -> bool:
        """检查是否为 AIOps 多指标异常检测策略.

        :param strategy_item: 策略配置
        :return: 是否为多指标异常检测策略
        """
        if (
            len(strategy_item["algorithms"]) > 0
            and strategy_item["algorithms"][0]["type"] == AlgorithmModel.AlgorithmChoices.HostAnomalyDetection
        ):
            return True

        return False

    @classmethod
    def check_use_technical_level_config(cls, strategy_item) -> bool:
        """检查是否应使用算法技术级别对应的触发、恢复配置."""

        return is_auto_level_intelligent_detect(strategy_item)

    @classmethod
    def select_level_config(cls, configs_map, strategy_item, candidate_levels):
        if cls.check_is_multi_indicator_strategy(strategy_item):
            return list(configs_map.values())[0]

        if cls.check_use_technical_level_config(strategy_item):
            return configs_map["2"]

        for level in map(str, candidate_levels):
            if level in configs_map:
                return configs_map[level]

        return configs_map[str(candidate_levels[0])]
