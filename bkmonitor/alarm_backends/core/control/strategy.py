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
from datetime import datetime

import arrow
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from alarm_backends.constants import CONST_MINUTES, CONST_ONE_HOUR, NO_DATA_LEVEL
from alarm_backends.core.cache import key
from alarm_backends.core.cache.calendar import CalendarCacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.item import Item
from alarm_backends.core.i18n import i18n
from bkmonitor.models.strategy import AlgorithmModel
from bkmonitor.utils import time_tools
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.errors.alarm_backends import StrategyItemNotFound

logger = logging.getLogger("core.control")


class Strategy:
    def __init__(self, strategy_id, default_config=None):
        self.id = self.strategy_id = strategy_id
        self._config = default_config

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = StrategyCacheManager.get_strategy_by_id(self.strategy_id) or {}
        return self._config

    @property
    def strategy_group_key(self) -> str:
        if not self.config.get("items"):
            return ""

        return self.config["items"][0].get("query_md5", "")

    @property
    def use_api_sdk(self) -> bool:
        for query_config in self.config["items"][0]["query_configs"]:
            if "intelligent_detect" in query_config:
                return bool(query_config["intelligent_detect"].get("use_sdk"))

        return False

    def get_interval(self) -> int:
        """
        获取策略周期
        """
        if not self.config.get("items"):
            return CONST_MINUTES

        min_interval = None
        for query_config in self.config["items"][0]["query_configs"]:
            if "agg_interval" not in query_config:
                continue

            # 如果是第一次循环，直接赋值
            if min_interval is None:
                min_interval = query_config["agg_interval"]
                continue

            # 如果当前循环的聚合间隔小于最小聚合间隔，更新最小聚合间隔
            if query_config["agg_interval"] < min_interval:
                min_interval = query_config["agg_interval"]

        return min_interval or CONST_MINUTES

    @cached_property
    def bk_tenant_id(self) -> str:
        return bk_biz_id_to_bk_tenant_id(self.bk_biz_id)

    @property
    def priority(self):
        return self.config.get("priority")

    @property
    def priority_group_key(self) -> str:
        return self.config.get("priority_group_key", "")

    @cached_property
    def is_service_target(self) -> bool:
        """
        判断是否是"服务"层
        """
        return self.config.get("scenario") in ("component", "service_module", "service_process")

    @cached_property
    def is_host_target(self) -> bool:
        """
        判断是否为"主机"层
        """
        return self.config.get("scenario") in ("os", "host_process")

    @cached_property
    def bk_biz_id(self) -> str:
        return self.config.get("bk_biz_id", "0")

    @cached_property
    def scenario(self) -> str:
        return self.config.get("scenario", "")

    @cached_property
    def name(self) -> str:
        return self.config.get("name") or _("--")

    @cached_property
    def labels(self) -> str:
        """策略标签"""
        return ",".join(self.config.get("labels", []))

    @cached_property
    def item(self) -> Item:
        if self.items:
            return self.items[0]
        return Item({}, self)

    @cached_property
    def items(self) -> list[Item]:
        results = []
        item_list = self.config.get("items") or []
        for item_config in item_list:
            results.append(Item(item_config, self))
        return results

    @cached_property
    def type(self) -> str:
        return self.config.get("type", "monitor")

    @cached_property
    def notice(self) -> dict:
        return self.config.get("notice", {})

    @cached_property
    def actions(self) -> list:
        return self.config.get("actions", [])

    def in_alarm_time(self, now_time=None) -> tuple[bool, str]:
        """
        是否在策略生效期间
        :return: bool, str
        """
        if not self.config:
            return True, ""
        trigger_configs = self.get_trigger_configs(self.config)
        if not trigger_configs:
            return True, ""

        trigger_config = list(trigger_configs.values())[0]
        uptime = trigger_config.get("uptime")
        if not uptime:
            # 拿不到配置，认为一直生效
            return True, ""

        i18n.set_biz(self.bk_biz_id)
        now_time = now_time or datetime.now()
        now_time_str = time_tools.strftime_local(now_time, _format="%H:%M")

        if not uptime["time_ranges"]:
            # 如果没配时间范围，就认为必定生效（因为正常来说至少配置一个，没配则说明没拿到，那就按默认逻辑处理）
            return True, ""

        time_ranges = []
        time_matched = False
        for time_range in uptime["time_ranges"]:
            try:
                start_time = arrow.get(time_range["start"], "HH:mm").format("HH:mm")
            except Exception:
                start_time = "00:00"

            try:
                end_time = arrow.get(time_range["end"], "HH:mm").format("HH:mm")
            except Exception:
                end_time = "23:59"

            time_ranges.append(f"{start_time}-{end_time}")

            if start_time <= end_time:
                if start_time <= now_time_str <= end_time:
                    # 情况1：开始时间 <= 结束时间，属于同一天的情况
                    time_matched = True
                    break
            elif start_time <= now_time_str or now_time_str <= end_time:
                # 情况2：开始时间 > 结束时间，属于跨天的情况
                time_matched = True
                break

        if not time_matched:
            # 一个时间范围都没匹配上，这个策略就不生效
            return False, _("当前时刻不在策略生效时间范围: {}").format(", ".join(time_ranges))

        # 检查生效日历和不生效日历
        active_calendar_ids = uptime.get("active_calendars") or []
        calendar_ids = uptime.get("calendars") or []

        # 获取生效日历事项
        active_item_messages = self._get_calendar_item_messages(active_calendar_ids)

        # 获取不生效日历事项
        inactive_item_messages = self._get_calendar_item_messages(calendar_ids)

        # 处理日历冲突逻辑
        # 优先级：生效日历 > 不生效日历
        if active_item_messages and inactive_item_messages:
            # 同时命中生效日历和不生效日历，生效日历优先
            return True, _("当前时刻同时命中告警日历和休息日历，告警日历优先生效: 告警日历[{}], 休息日历[{}]").format(
                ", ".join(active_item_messages), ", ".join(inactive_item_messages)
            )
        elif active_item_messages:
            # 只命中生效日历
            return True, _("当前时刻命中告警日历事项: {}").format(", ".join(active_item_messages))
        elif inactive_item_messages:
            # 只命中不生效日历
            return False, _("当前时刻命中日历休息事项: {}").format(", ".join(inactive_item_messages))
        elif active_calendar_ids:
            # 配置了生效日历但未命中任何事项
            return False, _("当前时刻未命中告警日历事项")

        return True, ""

    def _get_calendar_item_messages(self, calendar_ids: list[int]) -> list[str]:
        """
        获取日历事项消息列表

        :param calendar_ids: 日历ID列表（整数列表）
        :return: 日历事项消息列表，格式为 "日历名称(事项名称)"
        """
        item_messages: list[str] = []
        if not calendar_ids:
            return item_messages

        calendars: list[list[dict]] = CalendarCacheManager.mget(
            calendar_ids=calendar_ids, bk_tenant_id=self.bk_tenant_id
        )
        for items in calendars:
            for item in items:
                item_list: list[dict] = item.get("list", [])
                for _item in item_list:
                    item_messages.append(f"{_item['calendar_name']}({_item['name']})")

        return item_messages

    def gen_strategy_snapshot(self):
        """
        创建当前策略配置缓存快照， 返回快照存储的key
        """
        # 基于策略更新时间，判断策略是否有变更
        client = key.STRATEGY_SNAPSHOT_KEY.client
        update_time = self.config.get("update_time")
        snapshot_key = key.STRATEGY_SNAPSHOT_KEY.get_key(strategy_id=self.id, update_time=update_time)
        client.set(snapshot_key, json.dumps(self.config), ex=CONST_ONE_HOUR)
        setattr(self, "snapshot_key", snapshot_key)
        return snapshot_key

    @classmethod
    def get_strategy_snapshot_by_key(cls, snapshot_key, strategy_id=None):
        client = key.STRATEGY_SNAPSHOT_KEY.client
        if strategy_id:
            snapshot_key = key.SimilarStr(snapshot_key)
            snapshot_key.strategy_id = strategy_id
        snapshot = client.get(snapshot_key)
        if not snapshot:
            return None

        snapshot_strategy = json.loads(snapshot)
        return snapshot_strategy

    @classmethod
    def get_item_in_strategy(cls, strategy, item_id):
        """
        提取策略中对应item_id的监控项
        """
        # 获取产生了异常的监控项信息
        for item in strategy["items"]:
            if item["id"] == item_id:
                return item

        # 找不到对应的监控项，忽略这个异常点
        error_message = _("strategy({}), item({}) 监控项在快照数据中找不到").format(strategy["id"], item_id)
        logger.warning(error_message)
        raise StrategyItemNotFound({"strategy_id": strategy["id"], "item_id": item_id})

    @classmethod
    def get_check_window_unit(cls, item, default_check_unit=None):
        default_check_unit = default_check_unit or CONST_MINUTES
        if not item.get("query_configs"):
            # 如果不存在聚合条件，直接返回默认的
            return default_check_unit
        return min([query_config.get("agg_interval", default_check_unit) for query_config in item["query_configs"]])

    @staticmethod
    def get_trigger_configs(strategy: dict) -> dict[str, dict]:
        """
        获取不同级别算法的触发配置
        :return {
            "1": {
                "check_windows_size": 5,
                "trigger_count": 3,
            }
        }
        """
        is_aiops_algorithm = False
        items = strategy.get("items", [])
        if items:
            is_aiops_list = [
                algorithm["type"] in AlgorithmModel.AIOPS_ALGORITHMS
                for item in items
                for algorithm in item.get("algorithms") or []
            ]
            # is_aiops_list不为空时，算法类型全部都是AIOPS算法时，设置is_aiops_algorithm为True
            is_aiops_algorithm = all(is_aiops_list) and len(is_aiops_list) > 0

        trigger_config = {}
        for detect in strategy.get("detects") or []:
            # 如果只有AIOPS算法，则写死 check_window_size 为 5，trigger_count 为 1
            if is_aiops_algorithm:
                trigger_config[str(detect["level"])] = {
                    "check_window_size": 5,
                    "trigger_count": 1,
                    "uptime": detect["trigger_config"].get("uptime"),
                }
            else:
                trigger_config[str(detect["level"])] = {
                    "check_window_size": int(detect["trigger_config"]["check_window"]),
                    "trigger_count": int(detect["trigger_config"]["count"]),
                    "uptime": detect["trigger_config"].get("uptime"),
                }
        return trigger_config

    @staticmethod
    def get_recovery_configs(strategy: dict) -> dict[str, dict]:
        """
        获取不同级别的恢复配置
        :return {
            "1": {"check_windows": 5}
        }
        """
        recovery_config = {}
        for detect in strategy["detects"]:
            recovery_config[str(detect["level"])] = {
                "check_window_size": int(detect["recovery_config"]["check_window"]),
                "status_setter": detect["recovery_config"].get("status_setter", "recovery"),
            }
        return recovery_config

    @staticmethod
    def get_no_data_configs(item: dict):
        """
        获取无数据告警的触发配置
        :return: {
            "check_windows_size": 5,
            "trigger_count": 3,
            "level": 2,
        }
        """
        return {
            "check_window_size": int(item["no_data_config"]["continuous"]),
            "trigger_count": int(item["no_data_config"]["continuous"]),
            "level": int(item["no_data_config"].get("level", NO_DATA_LEVEL)),
        }

    def __getattr__(self, item):
        if item == "snapshot_key":
            return self.gen_strategy_snapshot()
        return super().__getattribute__(item)
