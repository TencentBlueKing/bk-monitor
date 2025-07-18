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
import os
import time
from collections import defaultdict

from celery.beat import ScheduleEntry
from django.conf import settings

from alarm_backends import constants
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.handlers import base
from alarm_backends.service.access import ACCESS_TYPE_TO_CLASS, AccessType
from alarm_backends.service.access.data.processor import AccessRealTimeDataProcess
from alarm_backends.service.access.tasks import (
    run_access_data,
    run_access_event_handler,
    run_access_incident_handler,
)
from bkmonitor.utils.beater import MonitorBeater
from bkmonitor.utils.common_utils import safe_int

logger = logging.getLogger("access")
REFRESH_STRATEGY_INFO = "refresh_agg_strategy_group_interval"
REFRESH_TARGETS = "refresh_targets"
REFRESH_INTERVAL = 90


class AccessBeater(MonitorBeater):
    def __init__(self, name, targets, service, entries=None):
        super().__init__(name, entries)
        self.targets = targets or []
        self.max_access_data_period = 58
        self.interval_map = {}
        self.service = service
        self.host_target = []

    def refresh_targets(self):
        """
        更新目标
        """
        if settings.ENVIRONMENT == constants.CONST_DEV:
            host_targets = self.service.query_host_targets()
            instance_targets = self.service.query_instance_targets(host_targets)
        else:
            host_targets, instance_targets = self.service.dispatch()
        self.targets = instance_targets
        self.host_target = host_targets

    def refresh_agg_strategy_group_interval(self):
        """
        更新聚合策略分组周期
        """

        def get_interval(s_ids: list[int]) -> tuple[list, bool]:
            """
            基于策略分组的策略获取item中的周期列表
            如果命中qos, 则返回标记
            :param s_ids: 策略ID列表
            :return: (周期列表, 是否QoS标记)
            """
            _interval_list = []
            _is_qos = False
            for s_id in s_ids:
                strategy = StrategyCacheManager.get_strategy_by_id(s_id)
                if strategy is None:
                    continue
                for item in strategy["items"]:
                    # 补充周期缓存
                    if item.get("query_configs", []):
                        for config in item["query_configs"]:
                            if config.get("agg_interval"):
                                _interval_list.append(config["agg_interval"])

                            if (
                                not _is_qos
                                and [config.get("data_source_label"), config.get("data_type_label")] in qos_labels
                            ):
                                _is_qos = True
            return _interval_list, _is_qos

        interval_map = defaultdict(set)
        qos_labels = getattr(settings, "QOS_DATASOURCE_LABELS") or []
        qos_interval_expand = getattr(settings, "QOS_INTERVAL_EXPAND", 3)
        strategy_groups = StrategyCacheManager.get_all_groups()
        targets = set(map(str, self.targets))
        for strategy_group_key, strategy_group in strategy_groups.items():
            is_qos = False
            strategy_group = json.loads(strategy_group)
            interval_list = strategy_group.pop("interval_list", [])
            # 获取策略对应数据源类型
            strategy_source = strategy_group.pop("strategy_source", [])
            strategy_source = strategy_source[0] if strategy_source else [None, None]
            for qos_label in qos_labels:
                data_source_label, data_type_label = qos_label
                if (data_source_label, data_type_label) == tuple(strategy_source):
                    is_qos = True
                    break

            bk_biz_id = strategy_group.pop("bk_biz_id", None)
            strategy_ids = strategy_group.keys()
            if bk_biz_id is not None:
                # 只要判定业务对应目标归属即可，因为策略组关联的策略归属同一业务
                if bk_biz_id not in self.host_target:
                    continue
            elif not targets & strategy_ids:
                # 业务字段未取到，则使用instance_targets 匹配
                continue

            if not interval_list:
                # 兼容方案，当策略缓存未存储interval_list时，去redis中获取策略中的interval
                interval_list, is_qos = get_interval(strategy_ids)

            min_interval = self.max_access_data_period
            # 异常边界考虑，当没有interval_list的时候这个策略不处理
            if interval_list:
                min_interval = min(self.max_access_data_period, *interval_list)
            else:
                logger.warning(f"strategy_group_key({strategy_group_key}) is invalid, will not processed")

            if is_qos:
                logger.warning(
                    f"strategy_group_key({strategy_group_key}) is qos, interval will be expanded with {qos_interval_expand}"
                )
                min_interval *= qos_interval_expand
            interval_map[min_interval].add(strategy_group_key)

        self.interval_map = interval_map
        for interval, group_keys in interval_map.items():
            schedule_dict = {
                "task": self.batch_access_data,
                "schedule": interval,
                "args": (interval,),
            }
            if interval not in self.entries:
                self.entries[interval] = ScheduleEntry(**schedule_dict)
            else:
                self.entries[interval].args = schedule_dict["args"]

        intervals = list(self.entries.keys())
        for interval in intervals:
            if interval not in interval_map and interval not in [REFRESH_STRATEGY_INFO, REFRESH_TARGETS]:
                self.entries.pop(interval)

    def batch_access_data(self, interval_key):
        """
        批量运行 Access data
        :param interval_key: 策略分组key(按周期)
        """
        strategy_group_keys = self.interval_map.get(interval_key) or []
        for _idx, strategy_group_key in enumerate(strategy_group_keys):
            run_access_data.delay(strategy_group_key, interval=interval_key)
            if _idx % (len(strategy_group_keys) // interval_key + 1) == 0:
                time.sleep(0.05)
        logger.info(
            f"[{self.display_name}](batch_access_data) publish group key with interval[{interval_key}] "
            f"total: {len(strategy_group_keys)}"
        )


class AccessHandler(base.BaseHandler):
    """
    AccessHandler
    """

    def __init__(self, targets=None, *args, **option):
        access_type = option.get("access_type")
        self.service = option.get("service")
        if access_type not in ACCESS_TYPE_TO_CLASS:
            raise Exception(f"Unknown Access Type({str(access_type)}).")

        self.access_type = access_type
        self.targets = targets or []
        self.option = option
        super().__init__(*args, **option)

    def handle_data(self):
        assert self.service is not None, "access data handler missing required argument: 'service'"

        access_beater = AccessBeater(name="access_beater", targets=self.targets, service=self.service)

        # 1. 刷新策略分组周期及目标
        access_beater.refresh_targets()
        # 2. 定时更新策略周期信息
        access_beater.entries[REFRESH_STRATEGY_INFO] = ScheduleEntry(
            task=access_beater.refresh_agg_strategy_group_interval, schedule=REFRESH_INTERVAL, args=()
        )

        # 3. 定时更新目标
        access_beater.entries[REFRESH_TARGETS] = ScheduleEntry(
            task=access_beater.refresh_targets, schedule=REFRESH_INTERVAL, args=()
        )

        # 4. 启动调度器
        access_beater.beater()

    def handle_real_time(self):
        p = AccessRealTimeDataProcess(self.service)
        p.process()

    def handle_event(self):
        # 将几种自定义事件的Data ID推入处理队列
        data_ids = [
            settings.GSE_BASE_ALARM_DATAID,
            settings.GSE_CUSTOM_EVENT_DATAID,
            settings.GSE_PROCESS_REPORT_DATAID,
        ]
        # 新增通过环境变量控制 dataid 禁用入口
        DISABLE_EVENT_DATAID = os.getenv("DISABLE_EVENT_DATAID", "0")
        disabled_data_ids = [safe_int(i) for i in DISABLE_EVENT_DATAID.split(",")]
        for data_id in data_ids:
            if data_id in disabled_data_ids:
                logger.info(f"dataid: {data_id} has been disabled in env[DISABLE_EVENT_DATAID]: {DISABLE_EVENT_DATAID}")
                continue
            self.run_access(run_access_event_handler, data_id)

    def handle_event_v2(self):
        # 直接在这里拉事件，并推送给worker处理
        from alarm_backends.service.access.event.event_poller import EventPoller

        EventPoller().start()

    def handle_incident(self) -> None:
        run_access_incident_handler(
            settings.BK_DATA_AIOPS_INCIDENT_BROKER_URL,
            settings.BK_DATA_AIOPS_INCIDENT_SYNC_QUEUE,
        )

    def handle(self):
        if self.access_type == AccessType.Data:
            self.handle_data()
        elif self.access_type == AccessType.RealTimeData:
            self.handle_real_time()
        elif self.access_type == AccessType.Event:
            self.handle_event_v2()
        elif self.access_type == AccessType.Incident:
            self.handle_incident()

    @staticmethod
    def run_access(access_func, *args):
        access_func(*args)


class AccessCeleryHandler(AccessHandler):
    """
    AccessCeleryHandler(run by celery worker)
    """

    @staticmethod
    def run_access(access_func, *args):
        access_func.delay(*args)
