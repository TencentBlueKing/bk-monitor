# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


class ServiceColorClassifier:
    COLORS = [
        "#96C989",
        "#F1CE1A",
        "#7EC7E7",
        "#E28D68",
        "#5766ED",
        "#EC6D93",
        "#8F87E1",
        "#6ECD94",
        "#F6A52C",
        "#5ACCCC",
        "#CC7575",
        "#4185EB",
        "#DD6CD2",
        "#8A88C1",
        "#7CB3A3",
        "#DBD84D",
        "#8DBAD3",
        "#D38D8D",
        "#4E76B1",
        "#BF92CB",
    ]

    def __init__(self):
        self._service_color_map = {}
        self._color_index = 0

    def next(self, service_name) -> str:
        color_index = self._service_color_map.get(service_name, self._color_index)
        color = self.COLORS[color_index]
        self._service_color_map[service_name] = color_index
        if color_index == self._color_index:
            self._color_index += 1
        if self._color_index == len(self.COLORS):
            self._color_index = 0
        return color
