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
from datetime import datetime
from typing import Dict

import arrow
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from alarm_backends.constants import CONST_MINUTES, CONST_ONE_HOUR, NO_DATA_LEVEL
from alarm_backends.core.cache import key
from alarm_backends.core.cache.calendar import CalendarCacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.item import Item
from alarm_backends.core.i18n import i18n
from bkmonitor.utils import time_tools
from core.errors.alarm_backends import StrategyItemNotFound

logger = logging.getLogger("core.control")


class Strategy(object):
    def __init__(self, strategy_id, default_config=None):
        self.id = self.strategy_id = strategy_id
        self._config = default_config

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = StrategyCacheManager.get_strategy_by_id(self.strategy_id) or {}
        return self._config

    @property
    def strategy_group_key(self):
        if not self.config.get("items"):
            return ""

        return self.config["items"][0].get("query_md5", "")

    @property
    def use_api_sdk(self):
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

    @property
    def priority(self):
        return self.config.get("priority")

    @property
    def priority_group_key(self):
        return self.config.get("priority_group_key", "")

    @cached_property
    def is_service_target(self):
        """
        判断是否是"服务"层
        """
        return self.config.get("scenario") in ("component", "service_module", "service_process")

    @cached_property
    def is_host_target(self):
        """
        判断是否为"主机"层
        """
        return self.config.get("scenario") in ("os", "host_process")

    @cached_property
    def bk_biz_id(self):
        return self.config.get("bk_biz_id", "0")

    @cached_property
    def scenario(self):
        return self.config.get("scenario", "")

    @cached_property
    def name(self):
        return self.config.get("name") or _("--")

    @cached_property
    def items(self):
        results = []
        item_list = self.config.get("items") or []
        for item_config in item_list:
            results.append(Item(item_config, self))
        return results

    @cached_property
    def type(self):
        return self.config.get("type", "monitor")

    @cached_property
    def notice(self):
        return self.config.get("notice", {})

    @cached_property
    def actions(self):
        return self.config.get("actions", [])

    def in_alarm_time(self, now_time=None) -> (bool, str):
        """
        是否在策略生效期间
        :return: bool
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

        # 再看看日历，是不是处于休息日
        calendar_ids = uptime.get("calendars") or []
        calendars = CalendarCacheManager.mget(calendar_ids)

        item_messages = []
        for items in calendars:
            # 只要命中了任意一个节假日，则这个告警就不生效
            for item in items:
                item_list = item.get("list", [])
                for _item in item_list:
                    item_messages.append(f'{_item["calendar_name"]}({_item["name"]})')

        if item_messages:
            return False, _("当前时刻命中日历休息事项: {}").format(", ".join(item_messages))

        return True, ""

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
        from bkmonitor.strategy.new_strategy import Strategy as StrategyClass

        client = key.STRATEGY_SNAPSHOT_KEY.client
        if strategy_id:
            snapshot_key = key.SimilarStr(snapshot_key)
            snapshot_key.strategy_id = strategy_id
        snapshot = client.get(snapshot_key)
        if not snapshot:
            return None

        snapshot_strategy = json.loads(snapshot)
        return StrategyClass.convert_v1_to_v2(snapshot_strategy)

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
    def get_trigger_configs(strategy: Dict) -> Dict[str, Dict]:
        """
        获取不同级别算法的触发配置
        :return {
            "1": {
                "check_windows_size": 5,
                "trigger_count": 3,
            }
        }
        """
        trigger_config = {}
        for detect in strategy["detects"]:
            trigger_config[str(detect["level"])] = {
                "check_window_size": int(detect["trigger_config"]["check_window"]),
                "trigger_count": int(detect["trigger_config"]["count"]),
                "uptime": detect["trigger_config"].get("uptime"),
            }
        return trigger_config

    @staticmethod
    def get_recovery_configs(strategy: Dict) -> Dict[str, Dict]:
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
    def get_no_data_configs(item: Dict):
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
        return super(Strategy, self).__getattribute__(item)
