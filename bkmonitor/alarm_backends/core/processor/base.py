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
from abc import ABCMeta

import six

from alarm_backends.core.cache import key


class BaseAbnormalPushProcessor(six.with_metaclass(ABCMeta, object)):
    """
    Base Processor
    """

    @staticmethod
    def push_abnormal_data(outputs, strategy_id, anomaly_signal_list=None):
        # detect.anomaly.signal: 异常信号队列
        # detect.anomaly.list.{strategy_id}.{item_id}.{level}: 异常结果信息队列
        anomaly_count = 0
        anomaly_signal_list = anomaly_signal_list or []
        pipeline = key.ANOMALY_LIST_KEY.client.pipeline(transaction=False)

        for item_id, outputs in six.iteritems(outputs):
            if outputs:
                outputs_data = [json.dumps(i) for i in outputs]
                anomaly_count += len(outputs_data)
                anomaly_signal_list.append("{strategy_id}.{item_id}".format(strategy_id=strategy_id, item_id=item_id))

                anomaly_queue_key = key.ANOMALY_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
                pipeline.lpush(anomaly_queue_key, *outputs_data)
                pipeline.expire(anomaly_queue_key, key.ANOMALY_LIST_KEY.ttl)

        if not anomaly_signal_list:
            return anomaly_count
        # 先推送anomaly list的数据
        pipeline.execute()

        # 再进行一次信号的推送，保证数据ready了之后再推送信号
        signal_pipeline = key.ANOMALY_SIGNAL_KEY.client.pipeline(transaction=False)
        anomaly_signal_key = key.ANOMALY_SIGNAL_KEY.get_key()
        signal_pipeline.lpush(anomaly_signal_key, *anomaly_signal_list)
        signal_pipeline.expire(anomaly_signal_key, key.ANOMALY_SIGNAL_KEY.ttl)
        signal_pipeline.execute()
        return anomaly_count
