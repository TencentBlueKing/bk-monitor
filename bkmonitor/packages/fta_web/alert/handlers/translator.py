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
import threading
from functools import reduce

from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.models import EventPluginV2, MetricListCache, StrategyModel
from bk_monitor_base.strategy import get_metric_id, parse_metric_id
from bkmonitor.utils.request import get_request_tenant_id
from constants.action import ActionPluginType, ActionSignal
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource

logger = logging.getLogger(__name__)


class AbstractTranslator:
    def __init__(self, name_format="{name}"):
        # 翻译名称格式，可选占位符：{id}, {name}
        self.name_format = name_format

    def translate(self, values: list) -> dict:
        """
        给出值的列表，返回每个值对应的翻译字典
        """
        raise NotImplementedError

    def translate_from_dict(self, records: list[dict], input_field: str, output_field: str):
        """
        从字典中获取待翻译字段，并输出到同一个字典的指定字段
        :param records: 数据列表
        :param input_field: 输入字段
        :param output_field: 输出字段
        """

        values = list({record[input_field] for record in records if record.get(input_field)})

        if not values:
            return

        try:
            translations = self.translate(values)
        except Exception as e:
            logger.exception("translate error, cls: %s, reason: %s", self.__class__, e)
            return

        for record in records:
            if not record.get(input_field):
                record[output_field] = None
            else:
                id = record[input_field]
                name = translations.get(id, id)

                # 对翻译进行格式化
                record[output_field] = self.name_format.format(id=id, name=name)


class MetricTranslator(AbstractTranslator):
    # 单条 SQL 内 OR 分支上限：既能命中索引，又不会因分支过多让优化器放弃索引
    QUERY_BATCH_SIZE = 50

    # 指标翻译只需要这些字段，避免把 description 等大字段读回来
    # bk_biz_id 必须一起取：同名指标择优要用，否则会触发 deferred 加载退化成 N+1
    TRANSLATE_FIELDS = (
        "bk_biz_id",
        "data_source_label",
        "data_type_label",
        "result_table_id",
        "metric_field",
        "metric_field_name",
        "related_id",
        "extend_fields",
        "data_label",
    )

    def __init__(self, bk_biz_ids: list[int] | None = None, *args, **kwargs):
        biz_ids = {biz_id for biz_id in (bk_biz_ids or []) if isinstance(biz_id, int)}
        # 显式指定业务 0 时，只取业务 0 的指标（保持原有语义）
        self.bk_biz_ids = sorted(biz_ids & {0})
        # 仅用于同名指标择优，不参与 SQL 过滤；-1（全部授权业务）不会进入这里
        self.scope_biz_ids = frozenset(biz_id for biz_id in biz_ids if biz_id > 0)
        super().__init__(*args, **kwargs)

    @staticmethod
    def _build_query_groups(values: list[str]) -> dict[frozenset, list[Q]]:
        """
        把 metric_id 解析成 Q，并按「查询条件列集合」分组。

        同组内每个 Q 的列集合完全一致，才能共用同一条索引。若把不同列集合的 Q 拼进同一个 OR
        （例如日志平台类的 related_id 与普通时序类的 result_table_id+metric_field），MySQL 无法
        做 index merge，会退化成单索引全扫，实测单次可达 12s。
        """
        query_groups: dict[frozenset, list[Q]] = {}
        for metric_id in values:
            try:
                metric = parse_metric_id(metric_id)
            except Exception:
                # 解析失败就跳过
                continue

            if "index_set_id" in metric:
                metric["related_id"] = metric.pop("index_set_id")
            if not metric:
                continue
            query_groups.setdefault(frozenset(metric), []).append(Q(**metric))
        return query_groups

    def _query_metrics(self, queries: list[Q], tenant_id: str) -> list:
        """执行一批列集合相同的 Q，只查询翻译需要的字段"""
        # 翻译场景不使用指标选择器的「请求业务去重」：它依赖 request 上下文、每批多 2 条探测 SQL，
        # 且会先于下面的 bk_biz_id 过滤排除业务 0 记录。
        metrics_queryset = (
            MetricListCache.objects.without_request_biz_dedup()
            .filter(bk_tenant_id=tenant_id)
            .filter(reduce(lambda x, y: x | y, queries))
        )
        if self.bk_biz_ids:
            metrics_queryset = metrics_queryset.filter(bk_biz_id__in=self.bk_biz_ids)
        return list(metrics_queryset.only(*self.TRANSLATE_FIELDS))

    def _translation_priority(self, metric) -> tuple:
        """同一 metric_id 命中多行时的择优顺序，返回值越小越优先。

        metric_id 不携带业务信息，跨业务的同名记录（如 result_table_id 为空的内置指标、
        容器指标）会解析出同一个 id；而翻译走的是 without_request_biz_dedup()，不再由
        manager 按 request.biz_id 隐藏业务 0 的内置指标，原来的"后写覆盖"又依赖返回顺序。
        这里用一组确定的优先级承接这两层语义，保证同一份数据每次得到同一个名称：

        1. 调用方业务范围（scope_biz_ids）内的业务优先，避免业务页显示成其他业务的同名指标；
        2. 业务自身的记录优先于业务 0 的内置记录，对应原 manager 去重的展示意图；
        3. bk_biz_id 升序兜底，结果不受数据库返回顺序和分批顺序影响。
        """
        return (
            metric.bk_biz_id not in self.scope_biz_ids,
            metric.bk_biz_id == 0,
            metric.bk_biz_id,
        )

    def translate(self, values: list[str]) -> dict:
        if settings.ROLE == "api":
            return {}
        if not values:
            return {}

        tenant_id = get_request_tenant_id()

        query_groups = self._build_query_groups(values)
        if not query_groups:
            # 没有需要查询的指标，则直接退出
            return {}

        all_metrics = []
        for field_names, queries in query_groups.items():
            for start in range(0, len(queries), self.QUERY_BATCH_SIZE):
                batch = queries[start : start + self.QUERY_BATCH_SIZE]
                try:
                    all_metrics.extend(self._query_metrics(batch, tenant_id))
                except Exception as e:
                    # 单批失败只跳过该批，避免一个异常导致整页指标都不翻译
                    logger.warning(
                        "MetricListCache query failed, skip %s metrics, fields: %s, reason: %s",
                        len(batch),
                        sorted(field_names),
                        e,
                        exc_info=True,
                    )

        metric_translations: dict[str, tuple[tuple, str]] = {}
        for metric in all_metrics:
            query_data = {
                "data_source_label": metric.data_source_label,
                "data_type_label": metric.data_type_label,
                "result_table_id": metric.result_table_id,
                "metric_field": metric.metric_field,
                "data_label": metric.data_label,
            }
            if metric.data_source_label == DataSourceLabel.BK_LOG_SEARCH:
                query_data.update(
                    {
                        "index_set_id": metric.related_id,
                    }
                )
            elif (metric.data_source_label, metric.data_type_label) == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
                query_data["custom_event_name"] = metric.extend_fields.get("custom_event_name", "")
            metric_id = get_metric_id(**query_data)

            priority = self._translation_priority(metric)
            current = metric_translations.get(metric_id)
            if current is None or priority < current[0]:
                metric_translations[metric_id] = (priority, metric.metric_field_name)

        return {value: metric_translations[value][1] if value in metric_translations else value for value in values}


class StrategyTranslator(AbstractTranslator):
    def translate(self, values: list[int]) -> dict:
        strategies = StrategyModel.objects.filter(id__in=values).values("id", "name")
        strategy_translations = {s["id"]: s["name"] for s in strategies}
        return {value: strategy_translations.get(int(value), value) for value in values}


class BizTranslator(AbstractTranslator):
    biz_map_cache = None
    lock = threading.Lock()

    def biz_map(self):
        with self.__class__.lock:
            if self.__class__.biz_map_cache is None:
                self.__class__.biz_map_cache = resource.space.get_space_map()
        return self.__class__.biz_map_cache

    def translate(self, values: list[int | str]) -> dict:
        biz_map = self.biz_map()
        result = {}
        for value in values:
            # 兼容 bk_biz_id 为字符串类型（ES Keyword 聚合返回的 bucket.key）
            lookup_key = value
            if isinstance(value, str):
                try:
                    lookup_key = int(value)
                except (ValueError, TypeError):
                    pass
            result[value] = biz_map[lookup_key]["display_name"] if lookup_key in biz_map else str(value)
        return result


class CategoryTranslator(AbstractTranslator):
    def translate(self, values: list[str]) -> dict:
        labels = resource.commons.get_label()
        label_translations = {}
        for outer in labels:
            for inner in outer["children"]:
                label_translations[inner["id"]] = f"{outer['name']}-{inner['name']}"
        return {value: label_translations.get(value, _("其他-其他")) for value in values}


class ActionSignalTranslator(AbstractTranslator):
    def translate(self, values: list) -> dict:
        return {value: ActionSignal.ACTION_SIGNAL_DICT.get(value, "--") for value in values}


class ActionPluginTypeTranslator(AbstractTranslator):
    def translate(self, values: list) -> dict:
        return {value: ActionPluginType.PLUGIN_TYPE_DICT.get(value, "--") for value in values}


class PluginTranslator(AbstractTranslator):
    def translate(self, values: list[str]) -> dict:
        plugins = {
            p.plugin_id: p.plugin_display_name
            for p in EventPluginV2.objects.filter(is_latest=True).only("plugin_id", "plugin_display_name")
        }
        plugins["bkmonitor"] = _("监控策略")
        return {value: plugins[str(value)] if str(value) in plugins else value for value in values}


class TopoNodeTranslator(AbstractTranslator):
    """拓扑节点翻译器，将 bk_topo_node 的值翻译为中文名称"""

    TYPE_LABEL_MAP = {
        "biz": _lazy("业务"),
        "set": _lazy("集群"),
        "module": _lazy("模块"),
    }

    def __init__(self, bk_biz_ids: list[int], *args, **kwargs):
        self.bk_biz_ids = bk_biz_ids
        super().__init__(*args, **kwargs)

    def translate(self, values: list[str]) -> dict:
        if not values:
            return {}

        # 按 type 分组收集 id
        grouped = {}
        for value in values:
            parts = str(value).split("|", 1)
            if len(parts) != 2:
                continue
            node_type, node_id = parts[0], parts[1]
            try:
                node_id = int(node_id)
            except (ValueError, TypeError):
                continue
            grouped.setdefault(node_type, []).append(node_id)

        # 批量查询各类型名称
        name_map = {}  # {原始值: 翻译后名称}
        if "biz" in grouped:
            biz_ids = grouped["biz"]
            try:
                businesses = api.cmdb.get_business(bk_biz_ids=biz_ids)
                for biz in businesses:
                    label = self.TYPE_LABEL_MAP.get("biz", "biz")
                    name_map[f"biz|{biz.bk_biz_id}"] = f"{label}|{biz.bk_biz_name}"
            except Exception:
                logger.exception("TopoNodeTranslator: failed to translate biz nodes")

        if "set" in grouped:
            set_ids = grouped["set"]
            try:
                params = [{"bk_biz_id": biz_id, "bk_set_ids": set_ids} for biz_id in self.bk_biz_ids]
                sets_list = api.cmdb.get_set.bulk_request(params)
                for sets in sets_list:
                    for s in sets:
                        label = self.TYPE_LABEL_MAP.get("set", "set")
                        name_map[f"set|{s.bk_set_id}"] = f"{label}|{s.bk_set_name}"
            except Exception:
                logger.exception("TopoNodeTranslator: failed to translate set nodes")

        if "module" in grouped:
            module_ids = grouped["module"]
            try:
                params = [{"bk_biz_id": biz_id, "bk_module_ids": module_ids} for biz_id in self.bk_biz_ids]
                modules_list = api.cmdb.get_module.bulk_request(params)
                for modules in modules_list:
                    for m in modules:
                        label = self.TYPE_LABEL_MAP.get("module", "module")
                        name_map[f"module|{m.bk_module_id}"] = f"{label}|{m.bk_module_name}"
            except Exception:
                logger.exception("TopoNodeTranslator: failed to translate module nodes")

        return {value: name_map.get(value, value) for value in values}
