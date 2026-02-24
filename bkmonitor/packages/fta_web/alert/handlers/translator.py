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
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import reduce

from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext as _

from bkmonitor.models import EventPluginV2, MetricListCache, StrategyModel
from bkmonitor.strategy.new_strategy import get_metric_id, parse_metric_id
from bkmonitor.utils.request import get_request_tenant_id
from constants.action import ActionPluginType, ActionSignal
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource
from common.decorators import db_safe_wrapper

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
    def __init__(self, bk_biz_ids: list[int] | None = None, *args, **kwargs):
        self.bk_biz_ids = list(set(bk_biz_ids or []) & {0})
        super().__init__(*args, **kwargs)

    @db_safe_wrapper
    def _execute_single_query(self, query: Q, tenant_id: str) -> list:
        """
        执行单个查询
        每个独立查询使用精确条件，能更好地利用复合索引
        使用 db_safe_wrapper 确保多线程环境下数据库连接安全
        """
        try:
            metrics_queryset = MetricListCache.objects.filter(bk_tenant_id=tenant_id).filter(query)
            if self.bk_biz_ids:
                metrics_queryset = metrics_queryset.filter(bk_biz_id__in=self.bk_biz_ids)
            # 只查询必要的字段
            return list(
                metrics_queryset.only(
                    "data_source_label",
                    "data_type_label",
                    "result_table_id",
                    "metric_field",
                    "metric_field_name",
                    "related_id",
                    "extend_fields",
                    "data_label",
                )
            )
        except Exception as e:
            # 捕获并静默处理查询异常：返回空列表以跳过该指标的翻译，避免异常传播影响其他并发查询
            logger.warning("MetricListCache query failed: %s", str(e))
            return []

    def translate(self, values: list[str]) -> dict:
        if settings.ROLE == "api":
            return {}
        if not values:
            return {}

        tenant_id = get_request_tenant_id()

        # 解析所有metric_id并构建查询条件
        queries = []
        for metric_id in values:
            try:
                metric = parse_metric_id(metric_id)
            except Exception:
                # 解析失败就跳过
                continue

            if "index_set_id" in metric:
                metric["related_id"] = metric["index_set_id"]
                del metric["index_set_id"]
            if metric:
                queries.append(Q(**metric))

        if not queries:
            # 没有需要查询的指标，则直接退出
            return {}

        all_metrics = []
        if len(queries) <= 3:
            # OR 查询条件较少，使用单次 OR 查询
            metrics_queryset = MetricListCache.objects.filter(bk_tenant_id=tenant_id).filter(
                reduce(lambda x, y: x | y, queries)
            )
            if self.bk_biz_ids:
                metrics_queryset = metrics_queryset.filter(bk_biz_id__in=self.bk_biz_ids)

            all_metrics = list(
                metrics_queryset.only(
                    "data_source_label",
                    "data_type_label",
                    "result_table_id",
                    "metric_field",
                    "metric_field_name",
                    "related_id",
                    "extend_fields",
                    "data_label",
                )
            )
        else:
            # OR 查询条件较多，拆分为并发查询
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_query = {
                    executor.submit(self._execute_single_query, query, tenant_id): query for query in queries
                }

                for future in as_completed(future_to_query):
                    all_metrics.extend(future.result())

        metric_translations = {}
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
            metric_translations[metric_id] = metric.metric_field_name

        return {value: metric_translations.get(value, value) for value in values}


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

    def translate(self, values: list[int]) -> dict:
        biz_map = self.biz_map()
        return {value: biz_map[value]["display_name"] if value in biz_map else str(value) for value in values}


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
