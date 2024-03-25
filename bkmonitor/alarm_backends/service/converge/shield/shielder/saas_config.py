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
import logging
from datetime import datetime

import arrow
from django.conf import settings
from django.utils.translation import ugettext as _

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.core.cache.shield import ShieldCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.i18n import i18n
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.models import ActionInstance, time_tools
from bkmonitor.utils import extended_json
from constants.shield import ShieldType

from .base import BaseShielder

logger = logging.getLogger("fta_action.shield")


class AlertShieldConfigShielder(BaseShielder):
    """
    监控SaaS配置的告警屏蔽
    """

    type = ShieldType.SAAS_CONFIG

    def __init__(self, alert: AlertDocument):
        self.alert = alert
        try:
            self.configs = ShieldCacheManager.get_shields_by_biz_id(self.alert.event.bk_biz_id)
            config_ids = ",".join([str(config["id"]) for config in self.configs])
            logger.info(
                "Get biz(%s) shield configs(%s) of alert(%s), ",
                self.alert.event.bk_biz_id,
                config_ids,
                self.alert.id,
            )
        except BaseException as error:
            self.configs = []
            logger.exception("failed to get shield configs: %s", str(error))

        self.shield_objs = []
        for config in self.configs:
            shield_obj = AlertShieldObj(config)
            if shield_obj.is_match(alert):
                self.shield_objs.append(shield_obj)
        shield_config_ids = ",".join([str(shield_obj.id) for shield_obj in self.shield_objs])
        self.is_global_shielder = None
        self.is_host_shielder = None
        self.detail = extended_json.dumps({"message": _("因为告警屏蔽配置({})屏蔽当前处理").format(shield_config_ids)})

    def is_matched(self):
        if GlobalShielder().is_matched():
            self.is_global_shielder = True
            self.detail = extended_json.dumps({"message": _("因系统全局屏蔽配置， 默认屏蔽当前处理")})
            return True

        if HostShielder(self.alert).is_matched():
            self.is_host_shielder = True
            self.detail = extended_json.dumps({"message": _("因当前主机状态为屏蔽告警，默认屏蔽当前处理")})
            return True

        return bool(self.shield_objs)

    def get_shield_left_time(self):
        """
        获取当前告警的屏蔽剩余时间
        :return:
        """
        if self.is_global_shielder or self.is_host_shielder:
            # 全局屏蔽的情况下
            return 0
        matched_config_left_time = self.cal_shield_left_time()
        if matched_config_left_time:
            return matched_config_left_time[0][1]
        return 0

    def cal_shield_left_time(self):
        """
        获取屏蔽配置ID，按屏蔽时长倒序排列
        """
        matched_config_left_time = []
        current_time = arrow.now()
        for shield_obj in self.shield_objs:
            # 计算剩余屏蔽时间
            matched_config_left_time.append((shield_obj.id, shield_obj.time_check.shield_left_time(current_time)))
        matched_config_left_time.sort(key=lambda s: s[1], reverse=True)
        return matched_config_left_time

    def list_shield_ids(self):
        if self.is_global_shielder or self.is_host_shielder:
            # 全局屏蔽的情况下直接返回
            return []
        matched_config_left_time = self.cal_shield_left_time()
        return [config[0] for config in matched_config_left_time]


class AlarmTimeShielder(BaseShielder):
    """
    根据事件配置的告警时间屏蔽
    """

    type = ShieldType.ALARM_TIME

    def __init__(self, action: ActionInstance):
        self.action = action
        self.detail = extended_json.dumps({"message": "not shielded"})

    def is_alarm_time(self):
        i18n.set_biz(self.action.bk_biz_id)
        now_time = time_tools.strftime_local(datetime.now(), _format="%H:%M:%S")

        [alarm_start_time, alarm_end_time] = self.action.inputs.get("time_range", "00:00:00--23:59:59").split("--")

        if alarm_start_time <= alarm_end_time:
            if alarm_start_time <= now_time <= alarm_end_time:
                # 情况1：开始时间 <= 结束时间，属于同一天的情况
                return True
        elif alarm_start_time <= now_time or now_time <= alarm_end_time:
            # 情况2：开始时间 > 结束时间，属于跨天的情况
            return True
        self.detail = extended_json.dumps(
            {"message": _("当前时间({})不在设置的处理时间范围[{}]内").format(now_time, self.action.inputs.get("time_range"))}
        )
        return False

    def is_strategy_uptime(self):
        strategy = Strategy(self.action.strategy_id)
        in_alarm_time, message = strategy.in_alarm_time()
        if in_alarm_time:
            return True
        self.detail = extended_json.dumps({"message": message})
        return False

    def is_matched(self):
        if self.is_alarm_time() and self.is_strategy_uptime():
            # 当前为通知时间，则不屏蔽，否则设置为屏蔽状态
            return False
        return True


class GlobalShielder(BaseShielder):
    def __init__(self):
        self.detail = extended_json.dumps({"message": _("全局屏蔽未开启")})

    def is_matched(self):
        if getattr(settings, "GLOBAL_SHIELD_ENABLED", False):
            self.detail = extended_json.dumps({"message": _("当前可能由于发布或变更进行了全局屏蔽")})
            return True
        return False


class HostShielder(BaseShielder):
    def __init__(self, alert: AlertDocument):
        self.alert = alert
        self.detail = extended_json.dumps({"message": _("当前主机屏蔽未开启")})

    def is_matched(self):

        if getattr(self.alert.event, "target_type", None) == "HOST":
            using_api = False
            ip = self.alert.event.ip
            bk_cloud_id = self.alert.event.bk_cloud_id
        elif "bcs_cluster_id" in getattr(self.alert.extra_info, "agg_dimensions", []):
            # 容器可补全IP告警
            dimension_dict = {dimension["key"]: dimension["value"] for dimension in self.alert.dimensions}
            ip = dimension_dict.get("ip", "")
            bk_cloud_id = dimension_dict.get("bk_cloud_id", None)
            # TODO(crayon) enrich 已经补充了 HostID 的维度，IP & 管控区域在动态主机场景下可能重复，直接用 HostID 更准
            # TODO(crayon) 下次修改，本次改动暂不引入新变更
            if not ip or bk_cloud_id is None:
                # 如果IP 为空或者 不存在云区域ID，忽略
                return False
            # 容器场景告警生成时间和主机纳管时间相邻，增加 API 请求兜底
            using_api = True
        else:
            # 不是host类型告警也不是容器相关的，忽略，不做判断
            return False

        host = HostManager.get(ip=ip, bk_cloud_id=bk_cloud_id, using_mem=True, using_api=using_api)

        if host and any([host.is_shielding, host.ignore_monitoring]):
            # 如果当前主机处于不监控（容器告警机器信息后期补全，所以在这里也进要行配置）或者不告警的状态，都统一屏蔽掉
            logger.info("alert(%s) is shielded because of host state is shielding(%s)", self.alert.id, host.bk_state)
            self.detail = extended_json.dumps({"message": _("当前主机在配置平台中设置了无告警状态")})
            return True
        elif not host and using_api:
            logger.warning(
                "alert(%s) is not shielded because of host(%s) not found",
                self.alert,
                HostManager.key_to_internal_value(ip, bk_cloud_id),
            )
        return False
