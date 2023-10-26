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
from typing import List, Dict, Optional


class Panel:
    id: str
    type: str
    title: str
    subTitle: str
    targets: List[Dict]
    options: Dict
    grid_pos: Dict

    def __init__(
        self,
        id: str,
        type: str,
        title: str,
        sub_title: str,
        targets: List[Dict],
        options: Dict,
        grid_pos: Optional[Dict],
        **kwargs
    ):
        self.id = id
        self.type = type
        self.title = title
        self.sub_title = sub_title
        self.targets = targets or []
        self.options = options
        self.grid_pos = grid_pos or {}

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "sub_title": self.sub_title,
            "targets": self.targets,
            "options": self.options,
            "grid_pos": self.grid_pos,
        }

    def to_grafana(self):
        return
