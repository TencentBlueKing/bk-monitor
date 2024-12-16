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


import arrow
import six


class DataPoint(object):
    """
    access 拉取的数据，在detect模块的一层封装
    """

    # 定义DataPoint必须拥有的属性
    context_field = ["value", "timestamp", "unit", "item"]

    def __init__(self, accessed_data, item):
        self.item = item
        self._raw_input = accessed_data
        for k, v in six.iteritems(accessed_data):
            if not k.startswith("__"):
                setattr(self, k, v)

    def as_dict(self):
        return self._raw_input

    # data_point attribute
    @property
    def unit(self):
        # 多指标不进行任何单位处理
        if len(self.item.data_sources) > 1:
            return ""
        return self.item.unit

    @property
    def timestamp(self):
        # alias for "time"
        return self.time

    def __str__(self):
        return "{record_id}:{value}".format(record_id=self.record_id, value=self.value)

    def __repr__(self):
        return str(self.as_dict())


class AnomalyDataPoint(object):
    """
    被detector处理后的DataPoint，如果是异常，则会变成AnomalyDataPoint。
    """

    def __init__(self, data_point, detector):
        self.data_point = data_point
        self.detector = detector
        self.anomaly_message = ""
        self.anomaly_time = arrow.utcnow().format("YYYY-MM-DD HH:mm:ss")
        self.strategy_snapshot_key = ""
        self.child_detector = []
        self.context = {}
