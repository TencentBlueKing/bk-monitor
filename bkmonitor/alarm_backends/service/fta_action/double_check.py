"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Dict, Type

from alarm_backends.core.control.mixins.double_check import DoubleCheckStrategy
from constants.action import NoticeWay

if TYPE_CHECKING:
    from bkmonitor.documents import AlertDocument

logger = logging.getLogger(__name__)


@dataclass
class SuspectedMissingPoints:
    alert: "AlertDocument"

    # 通知渠道降级序列，优先级从高到低
    NOTICE_WAY_DEGRADE_SEQUENCE: ClassVar[list] = [
        NoticeWay.VOICE,
        NoticeWay.SMS,
        NoticeWay.WEIXIN,
        NoticeWay.QY_WEIXIN,
        NoticeWay.WX_BOT,
        NoticeWay.MAIL,
    ]

    def handle(self, inputs: dict):
        """疑似数据缺失"""
        notify_info = inputs.get("notify_info", {})
        if not notify_info:
            logger.debug("Alert<%s>-<%s> 可能不需要通知，跳过二次处理", self.alert.id, self.alert.alert_name)
            return

        if NoticeWay.VOICE not in notify_info:
            logger.debug("Alert<%s>-<%s> 不需要语音通知，跳过二次处理", self.alert.id, self.alert.alert_name)
            return

        # 通知降级，同时保持当前通知组，但由于 VOICE 通知组内部有顺序，所以需要先拆开
        notify_group = set()
        for group in notify_info.pop(NoticeWay.VOICE):
            if not isinstance(group, list):
                notify_group.add(group)
                continue

            for g in group:
                notify_group.add(g)

        voice_index = self.NOTICE_WAY_DEGRADE_SEQUENCE.index(NoticeWay.VOICE)
        # 当存在降级通知方式时，找到最接近的告警组将当前通知组塞入
        for i in range(voice_index, len(self.NOTICE_WAY_DEGRADE_SEQUENCE)):
            if self.NOTICE_WAY_DEGRADE_SEQUENCE[i] in notify_info:
                # NOTE: 当前使用集合保证通知人不重复，但可能会改变原有的告警顺序
                # 但由于除了语音通知，其他通知渠道均对通知顺序不敏感，所以不做额外保证
                existed = set(notify_info[self.NOTICE_WAY_DEGRADE_SEQUENCE[i]])
                notify_info[self.NOTICE_WAY_DEGRADE_SEQUENCE[i]] = list(existed.union(notify_group))
                logger.info(
                    "由于二次确认怀疑告警<%s-%s>触发时数据存在缺失，故将语音通知降级处理，降级后的通知配置: %s",
                    self.alert.id,
                    self.alert.alert_name,
                    notify_info,
                )
                return

        # 当不存在其他通知方式时，找到最接近的告警组将当前通知组直接塞入
        notify_info[self.NOTICE_WAY_DEGRADE_SEQUENCE[voice_index + 1]] = list(notify_group)
        logger.info(
            "由于二次确认怀疑告警<%s-%s>触发时数据存在缺失，故将语音通知降级处理，降级后的通知配置: %s",
            self.alert.id,
            self.alert.alert_name,
            notify_info,
        )
        return


@dataclass
class DoubleCheckHandler:
    alert: "AlertDocument"
    double_check_result_handle_map: ClassVar[Dict[str, Type]] = {
        "SUSPECTED_MISSING_POINTS": SuspectedMissingPoints,
    }

    @property
    def tags(self) -> dict:
        return {t["key"]: t["value"] for t in getattr(self.alert.event, "tags", [])}

    def handle(self, inputs: dict):
        """针对告警二次确认结果做相关处理"""
        if DoubleCheckStrategy.DOUBLE_CHECK_CONTEXT_KEY not in self.tags:
            logger.debug("Alert<%s>-<%s> 不需要二次确认处理", self.alert.id, self.alert.alert_name)
            return

        double_check_result = self.tags[DoubleCheckStrategy.DOUBLE_CHECK_CONTEXT_KEY]
        handle_cls = self.double_check_result_handle_map.get(double_check_result, None)
        if handle_cls is None:
            logger.warning("未知二次确认结果: %s, 请在链路上游检查二次确认逻辑", double_check_result)
            return

        handle_cls(self.alert).handle(inputs)
