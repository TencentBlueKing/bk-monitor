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
from abc import ABC
from typing import Any, Dict, List, Optional, Union

from django.utils.translation import ugettext as _

from bkmonitor.models import MetricListCache
from constants.data_source import DATA_CATEGORY
from core.drf_resource import resource

logger = logging.getLogger(__name__)


class DictAble(ABC):
    __fields__ = []

    def __init__(self, **kwargs):
        self.extend_data = kwargs

    def __len__(self) -> int:
        return len(self.__fields__) + len(self.extend_data)

    def __getitem__(self, item: str):
        if hasattr(self, item):
            return getattr(self, item)

        if item in self.extend_data:
            return self.extend_data[item]

        raise KeyError("{} not found".format(repr(item)))

    def __iter__(self) -> (str, Any):
        for field in self.__fields__:
            yield field, self.__getitem__(field)

        for field in self.extend_data:
            yield field, self.extend_data[field]


class BasePanel(DictAble):
    """
    Grafana Panel配置

    开发版本: 6.7.1
    参考文档: https://grafana.com/docs/grafana/latest/reference/dashboard/
    """

    __fields__ = ["id", "type", "title", "gridPos", "datasource", "targets"]

    type = ""

    def __init__(self, type: str, title: str, gridPos: Dict, datasource: Optional[str] = None, id: int = 0, **kwargs):
        self.id = id
        self.type = type
        self.title = title
        self.gridPos = gridPos
        self.datasource = datasource
        self.targets = []
        super(BasePanel, self).__init__(**kwargs)


class GraphPanel(BasePanel):
    """
    Grafana Graph配置
    """

    __fields__ = ["id", "type", "title", "gridPos", "datasource", "lines", "bars", "points", "targets", "thresholds"]

    type = "graph"

    def __init__(
        self,
        title: str,
        gridPos: Dict,
        datasource: Optional[str] = None,
        id: int = 0,
        lines: bool = True,
        bars: bool = False,
        points: bool = False,
        thresholds: Optional[List] = None,
        **kwargs,
    ):
        self.lines = lines
        self.bars = bars
        self.points = points
        self.thresholds = thresholds if thresholds else []
        super(GraphPanel, self).__init__(self.type, title, gridPos, datasource, id, **kwargs)


class StatPanel(BasePanel):
    """
    Grafana Stat配置
    """

    __fields__ = ["id", "type", "title", "gridPos", "datasource", "options", "targets"]

    type = "stat"

    def __init__(
        self, title: str, gridPos: Dict, datasource: Optional[str] = None, id: int = 0, options: Dict = None, **kwargs
    ):
        self.options = options if options else {"fieldOptions": {}, "graphMode": "none"}
        super(StatPanel, self).__init__(self.type, title, gridPos, datasource, id, **kwargs)


class BarGaugePanel(BasePanel):
    """
    Grafana Bar Gauge配置
    """

    __fields__ = ["id", "type", "title", "gridPos", "datasource", "options", "targets"]

    type = "bargauge"

    def __init__(
        self, title: str, gridPos: Dict, datasource: Optional[str] = None, id: int = 0, options: Dict = None, **kwargs
    ):
        self.options = (
            options
            if options
            else {"fieldOptions": {}, "orientation": "horizontal", "showUnfilled": True, "displayMode": "gradient"}
        )
        super(BarGaugePanel, self).__init__(self.type, title, gridPos, datasource, id, **kwargs)


class PanelFactory:
    """
    图表工厂
    """

    PanelClasses = {
        "graph": GraphPanel,
        "stat": StatPanel,
        "bargauge": BarGaugePanel,
    }

    PanelType = Union[BasePanel, GraphPanel, StatPanel, BarGaugePanel]

    @classmethod
    def create(cls, config: Union[Dict, PanelType]) -> "PanelFactory.PanelType":
        if isinstance(config, BasePanel):
            return config

        return cls.PanelClasses.get(config["type"], BasePanel)(**config)

    @classmethod
    def bulk_create(cls, configs: List[Union[Dict, PanelType]]) -> "List[PanelFactory.PanelType]":
        return [cls.create(cls.create(config)) for config in configs]


class GrafanaDashboard(DictAble):
    """
    Grafana仪表盘配置

    开发版本: 6.7.1
    参考文档: https://grafana.com/docs/grafana/latest/reference/dashboard/
    """

    DefaultSchemaVersion = 22

    __fields__ = [
        "title",
        "editable",
        "refresh",
        "style",
        "tags",
        "timezone",
        "graphTooltip",
        "templating",
        "version",
        "schemaVersion",
        "time",
        "timepicker",
        "links",
        "panels",
        "annotations",
    ]

    def __init__(
        self,
        title: str,
        editable: bool = True,
        refresh: Union[bool, str] = False,
        style: str = "light",
        tags: Optional[List] = None,
        timezone: str = "",
        graphTooltip: int = 0,
        version: int = 1,
        schemaVersion: int = DefaultSchemaVersion,
        panels: Optional[List] = None,
        templating: Optional[Dict] = None,
        annotations: Optional[Dict] = None,
        links: Optional[List] = None,
        time: Optional[Dict] = None,
        timepicker: Optional[Dict] = None,
        **kwargs,
    ):
        self.title = title
        self.editable = editable
        self.refresh = refresh
        self.style = style
        self.tags = tags if tags else []
        self.timezone = timezone
        self.graphTooltip = graphTooltip
        self.version = version
        self.schemaVersion = schemaVersion

        self.time = time if time else {"from": "now-6h", "to": "now"}
        self.timepicker = timepicker if timepicker else {}

        self.links = links if links else []
        self._panels = PanelFactory.bulk_create(panels) if panels else []
        self.templating = templating if templating else {"list": []}
        self.annotations = annotations if annotations else {"list": []}
        self.kwargs = kwargs

        super(GrafanaDashboard, self).__init__()

    @property
    def panels(self):
        return [dict(panel) for panel in self._panels]

    @panels.setter
    def panels(self, data: List[Union[PanelFactory.PanelType, Dict]]):
        self._panels = PanelFactory.bulk_create(data)

    def add_panel(self, panel: Union[PanelFactory.PanelType, Dict]):
        """
        添加图表（对象）
        """
        panel = PanelFactory.create(panel)
        panel.id = len(self._panels) + 1
        self._panels.append(PanelFactory.create(panel))


class GrafanaMonitorTarget:
    """
    Grafana 蓝鲸监控时序数据源 - 查询参数结构
    """

    def __init__(
        self,
        data_source_label: str,
        data_type_label: str,
        result_table_id: str,
        metric_field: str,
        method: str,
        period: int = 60,
        offset: str = "",
        dimensions: Optional[List[str]] = None,
        conditions: List[Dict] = None,
        function: Dict = None,
        alias: str = "",
    ):
        self.data_source_label = data_source_label
        self.data_type_label = data_type_label
        self.result_table_id = result_table_id
        self.metric_field = metric_field
        self.method = method
        self.period = period
        self.offset = offset
        self.function = function if function else {"rank": {"sort": "", "limit": 0}}
        self.conditions = conditions if conditions else []
        self.dimensions = dimensions if dimensions else []
        self.alias = alias

        super(GrafanaMonitorTarget, self).__init__()

    @classmethod
    def serialize(cls, grafana_target):
        raise NotImplementedError

    @classmethod
    def deserialize_condition(cls, metric: MetricListCache, conditions):
        """
        生成grafana 蓝鲸监控时序型插件所需condition结构
        """
        dimensions = metric.dimensions

        configs = []
        for index, condition in enumerate(conditions):
            config = []
            if index != 0:
                config.append(
                    {
                        "key": f"{index}0",
                        "type": "condition",
                        "value": condition.get("condition", "and"),
                        "list": [{"id": "and", "name": "AND"}, {"id": "or", "name": "OR"}],
                    }
                )

            config.extend(
                [
                    {"key": f"{index}1", "type": "key", "value": condition["key"], "list": dimensions},
                    {"key": f"{index}2", "type": "method", "value": condition["method"], "list": []},
                    {"key": f"{index}3", "type": "value", "value": condition["value"], "list": []},
                ]
            )
            configs.append(config)
        return configs

    @classmethod
    def deserialize(cls, target: "GrafanaMonitorTarget", index):
        """
        生成grafana 蓝鲸监控时序型插件所需target结构
        """
        labels = resource.commons.get_label()

        metric = MetricListCache.objects.filter(
            data_source_label=target.data_source_label,
            data_type_label=target.data_type_label,
            result_table_id=target.result_table_id,
            metric_field=target.metric_field,
        ).first()

        if not metric:
            logger.error(
                "生成grafana配置失败，查询指标为空, result_table_id: {}, metric_field: {}".format(
                    target.result_table_id, target.metric_field
                )
            )
            return

        # 获取数据源分类
        data_source_key = "other"
        data_source_name = _("其他")
        for category in DATA_CATEGORY:
            if (
                category["data_source_label"] == metric.data_source_label
                and category["data_type_label"] == metric.data_type_label
            ):
                data_source_name = str(category["name"])
                data_source_key = f"{metric.data_source_label}.{metric.data_type_label}"
                continue

        # 查找所属监控对象组
        group_id = ""
        for label in labels:
            for option in label["children"]:
                if option["id"] == metric.result_table_label:
                    group_id = label["id"]

        config = {
            "data": {
                "alias": target.alias,
                "conditions": cls.deserialize_condition(metric, target.conditions),
                "dimensions": target.dimensions,
                "func": target.function,
                "method": target.method,
                "offset": target.offset,
                "period": target.period,
                "target": {"expandKeys": [], "realValues": [], "treeData": [], "values": []},
                "metric": {
                    "id": [data_source_key, metric.related_id, metric.result_table_id, metric.metric_field],
                    "labels": [
                        data_source_name,
                        metric.related_name,
                        metric.result_table_name,
                        metric.metric_field_name,
                    ],
                    "list": [],
                },
                "monitorObject": {"groupId": group_id, "id": metric.result_table_label},
            },
            "datasourceId": "bkmonitor-timeseries-datasource",
            "name": _("蓝鲸监控 - 时序数据"),
            "refId": chr(ord("A") + index),
        }
        return config


if __name__ == "__main__":
    import json

    dash = GrafanaDashboard(_("默认仪表盘"))
    dash.add_panel(
        {"id": 0, "type": "graph", "title": _("CPU总使用率"), "lines": True, "gridPos": {"x": 0, "y": 0, "h": 4, "w": 8}}
    )
    print(json.dumps(dict(dash), ensure_ascii=False, indent=2))
