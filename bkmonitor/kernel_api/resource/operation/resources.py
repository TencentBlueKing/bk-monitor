"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

运营数据 MCP 对外工具（3 个通用 Resource）：

- ListOperationMetricsResource   发现：返回运营指标目录
- GetOperationMetricResource     取值：按 metric_key 取单个指标值
- GetOperationOverviewResource   批量：按分类批量取值（单指标失败降级）
"""

from django.conf import settings
from django.core.cache import cache
from rest_framework import serializers

from core.drf_resource.base import Resource, logger

from .registry import (
    MetricCategory,
    OperationMetric,
    get_metric,
    iter_metrics,
)

# 当前部署环境标识（可选）。部署方可在 settings 设置 OPERATION_MCP_ENV = "bkte" / "bkop" / "sg"，
# 用于隐藏本环境不存在的指标（如未部署 eBPF / doris）。未设置时不做环境过滤。
_CATEGORY_CHOICES = [c.value for c in MetricCategory]


def _current_env() -> str | None:
    return getattr(settings, "OPERATION_MCP_ENV", None)


def _metric_catalog_item(metric: OperationMetric) -> dict:
    """目录条目（不含取值）。"""
    return {
        "key": metric.key,
        "category": metric.category.value,
        "name": metric.name,
        "unit": metric.unit,
        "description": metric.description,
        "handler_type": metric.handler_type.value,
        "supported_envs": metric.supported_envs,
        "biz_scoped": metric.biz_scoped,
        "slow": metric.slow,
        "programmable": metric.handler is not None,
        "note": metric.note,
    }


class ListOperationMetricsResource(Resource):
    """运营数据MCP--运营指标目录。返回全部可用运营指标的元信息，可按分类过滤。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID(鉴权用)")
        category = serializers.ChoiceField(
            choices=_CATEGORY_CHOICES, required=False, allow_blank=True, label="指标分类"
        )

    def perform_request(self, validated_request_data):
        category = validated_request_data.get("category") or None
        env = _current_env()
        items = [_metric_catalog_item(m) for m in iter_metrics(category=category, env=env)]
        logger.info("ListOperationMetricsResource: list %s operation metrics, category->[%s]", len(items), category)
        return {"list": items, "total": len(items)}


class GetOperationMetricResource(Resource):
    """运营数据MCP--取单个运营指标值。bk_biz_id 仅用于 MCP 鉴权，平台总量类指标不按业务过滤。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID(鉴权用)")
        metric_key = serializers.CharField(required=True, label="运营指标 key")
        end_time = serializers.IntegerField(
            required=False, label="截止时间戳(秒)，缺省为当前时间；显式传入则旁路缓存查历史点"
        )

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        metric_key = validated_request_data["metric_key"]
        end_time = validated_request_data.get("end_time")

        metric = get_metric(metric_key)
        if metric is None:
            raise serializers.ValidationError({"metric_key": f"unknown metric_key: {metric_key}"})

        if not metric.is_supported(_current_env()):
            raise serializers.ValidationError({"metric_key": f"metric '{metric_key}' is not supported in current env"})

        result = {
            "key": metric.key,
            "name": metric.name,
            "unit": metric.unit,
            "category": metric.category.value,
            "handler_type": metric.handler_type.value,
            "note": metric.note,
            "value": None,
        }

        if metric.handler is None:  # MANUAL：暂无法程序化
            result["programmable"] = False
            return result

        result["programmable"] = True
        result["value"] = self._resolve_value(metric, bk_biz_id, end_time)
        return result

    @staticmethod
    def _resolve_value(metric: OperationMetric, bk_biz_id: int, end_time: int | None):
        # 仅在"取当前值"（未显式指定 end_time）时启用缓存
        use_cache = metric.cache_ttl > 0 and end_time is None
        cache_key = f"operation_mcp:metric:{metric.key}:{bk_biz_id}" if use_cache else None

        if cache_key:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        logger.info(
            "GetOperationMetricResource: resolve metric->[%s], bk_biz_id->[%s], slow->[%s]",
            metric.key,
            bk_biz_id,
            metric.slow,
        )
        value = metric.handler(bk_biz_id=bk_biz_id, end_time=end_time)

        if cache_key and value is not None:
            cache.set(cache_key, value, metric.cache_ttl)
        return value


class GetOperationOverviewResource(Resource):
    """运营数据MCP--批量取运营指标。按分类批量返回，单指标失败降级到 error 字段不影响整批。
    默认跳过慢查询指标（slow=True），需要时置 include_slow=true 单独纳入。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID(鉴权用)")
        category = serializers.ChoiceField(
            choices=_CATEGORY_CHOICES, required=False, allow_blank=True, label="指标分类"
        )
        include_slow = serializers.BooleanField(required=False, default=False, label="是否纳入慢查询指标")
        end_time = serializers.IntegerField(required=False, label="截止时间戳(秒)")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        category = validated_request_data.get("category") or None
        include_slow = validated_request_data.get("include_slow") or False
        end_time = validated_request_data.get("end_time")
        env = _current_env()

        results = []
        for metric in iter_metrics(category=category, env=env):
            item = {
                "key": metric.key,
                "name": metric.name,
                "unit": metric.unit,
                "category": metric.category.value,
                "value": None,
                "error": None,
            }

            if metric.handler is None:
                item["error"] = "manual metric, no programmatic handler"
                results.append(item)
                continue

            if metric.slow and not include_slow:
                item["error"] = "slow metric skipped, set include_slow=true or query individually"
                results.append(item)
                continue

            try:
                item["value"] = metric.handler(bk_biz_id=bk_biz_id, end_time=end_time)
            except Exception as exc:  # noqa: BLE001 单指标失败降级，不影响整批
                logger.exception("GetOperationOverviewResource: metric->[%s] failed", metric.key)
                item["error"] = str(exc)
            results.append(item)

        return {"list": results, "total": len(results)}
