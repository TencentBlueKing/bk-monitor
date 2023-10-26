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
from typing import List

from bkmonitor.models import ActionInstance
from bkmonitor.documents import AlertDocument
from .shielder import AlertShieldConfigShielder, AlarmTimeShielder, GlobalShielder


class ShieldManager(object):
    """
    屏蔽管理
    """

    Shielders = (AlertShieldConfigShielder, AlarmTimeShielder)

    @classmethod
    def shield(cls, action_instance: ActionInstance, alerts: List[dict] = None):
        """
        屏蔽
        :param alerts: 告警的快照
        :param action_instance: 告警
        """
        # 先做全局屏蔽的检测
        global_shielder = GlobalShielder()
        if global_shielder.is_matched():
            return True, global_shielder

        if alerts:
            # 默认使用快照内容，快照没有，再从DB获取
            alerts = [AlertDocument(**alert) for alert in alerts]
        else:
            alerts = AlertDocument.mget(ids=action_instance.alerts)

        for shielder_cls in cls.Shielders:
            if shielder_cls == AlertShieldConfigShielder:
                for alert in alerts:
                    # 关联多告警的内容，只要有其中一个不满足条件，直接就屏蔽
                    alert.strategy_id = alert.strategy_id or action_instance.strategy_id
                    shielder = shielder_cls(alert)
                    if shielder.is_matched():
                        return True, shielder
            else:
                shielder = shielder_cls(action_instance)
                if shielder.is_matched():
                    return True, shielder
        return False, None
