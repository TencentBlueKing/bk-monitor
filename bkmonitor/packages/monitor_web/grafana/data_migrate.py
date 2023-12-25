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
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BasePanel:
    """
    Grafana Panel配置

    开发版本: 9.1.0
    参考文档: https://grafana.com/docs/grafana/latest/reference/dashboard/
    """

    type = ""

    def __init__(self, type: str, title: str, gridPos: Dict, datasource: Optional[str] = None, id: int = 0, **kwargs):
        self.id = id
        self.type = type
        self.title = title
        self.gridPos = gridPos
        self.datasource = datasource
        self.targets = []

    def to_dict(self):
        pass


class TimeSeriesPanel(BasePanel):
    """
    Grafana Graph配置
    """

    type = "timeseries"

    def __init__(
        self,
        title: str,
        gridPos: Dict,
        datasource: Optional[str] = None,
        id: int = 0,
        draw_style: str = "line",
        fill_opacity: int = 0,
        min_y: Optional[int] = None,
        **kwargs,
    ):
        self.draw_style = draw_style
        self.fill_opacity = fill_opacity
        self.min_y = min_y

        super(TimeSeriesPanel, self).__init__(self.type, title, gridPos, datasource, id, **kwargs)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "gridPos": self.gridPos,
            "datasource": self.datasource,
            "targets": self.targets,
            "options": {
                "tooltip": {"mode": "single", "sort": "none"},
                "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom", "calcs": []},
            },
            "fieldConfig": {
                "defaults": {
                    "custom": {
                        "drawStyle": self.draw_style,
                        "lineInterpolation": "linear",
                        "barAlignment": 0,
                        "lineWidth": 1,
                        "fillOpacity": self.fill_opacity,
                        "gradientMode": "none",
                        "spanNulls": False,
                        "showPoints": "auto",
                        "pointSize": 5,
                        "stacking": {"mode": "none", "group": "A"},
                        "axisPlacement": "auto",
                        "axisLabel": "",
                        "axisColorMode": "text",
                        "scaleDistribution": {"type": "linear"},
                        "axisCenteredZero": False,
                        "hideFrom": {"tooltip": False, "viz": False, "legend": False},
                        "thresholdsStyle": {"mode": "off"},
                    },
                    "color": {"mode": "palette-classic"},
                    "mappings": [],
                    "thresholds": {"mode": "absolute", "steps": [{"value": None, "color": "green"}]},
                    "min": self.min_y,
                },
                "overrides": [],
            },
        }
