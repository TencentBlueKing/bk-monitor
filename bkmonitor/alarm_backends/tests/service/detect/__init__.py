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
import random


class DataPoint:
    def __init__(self, value, timestamp, unit, item):
        self.value = value
        self.timestamp = timestamp
        self.unit = unit
        self.item = item
        self.record_id = "".join(random.choice("abcdefg123456") for i in range(1, 16)) + f".{timestamp}"

    def as_dict(self):
        return self.__dict__
