# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import logging

from django.conf import settings

from alarm_backends.core.cache import key
from bkmonitor.utils.common_utils import count_md5

logger = logging.getLogger("access.qos")


class QoSMixin(object):
    @classmethod
    def hash_alarm_by_match_info(cls, event_record, strategy_id, item_id):
        return count_md5(
            [
                event_record.bk_biz_id,
                strategy_id,
                item_id,
                event_record.data["data"]["dimensions"]["bk_target_ip"],
                event_record.level,
            ]
        )

    def check_qos(self, check_client=None):
        client = check_client or key.QOS_CONTROL_KEY.client
        if not client.exists(key.QOS_CONTROL_KEY.get_key()):
            return False

        new_record_list = []
        for event_record in self.record_list:
            for item in event_record.items:
                strategy_id = item.strategy.id
                item_id = item.id
                if not event_record.is_retains[item_id] or event_record.inhibitions[item_id]:
                    continue
                dimensions_md5 = self.hash_alarm_by_match_info(event_record, strategy_id, item_id)
                try:
                    count_of_alarm = client.hincrby(
                        key.QOS_CONTROL_KEY.get_key(), key.QOS_CONTROL_KEY.get_field(dimensions_md5=dimensions_md5), 1
                    )
                    if count_of_alarm > settings.QOS_DROP_ALARM_THREADHOLD:
                        logger.warning(
                            "qos drop alarm: cc_biz_id(%s), host(%s), " "strategy_id(%s), item_id(%s), level(%s)",
                            event_record.bk_biz_id,
                            event_record.data["data"]["dimensions"]["bk_target_ip"],
                            strategy_id,
                            item_id,
                            event_record.level,
                        )
                    else:
                        new_record_list.append(event_record)
                except Exception as err:
                    new_record_list.append(event_record)
                    logger.exception(err)

        self.record_list = new_record_list
        return True
