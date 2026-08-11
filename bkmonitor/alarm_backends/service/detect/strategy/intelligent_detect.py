"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
IntelligentDetect：智能异常检测算法基于计算平台的计算结果，再基于结果表的is_anomaly{1,2,3}来进行判断。
"""
import concurrent.futures
import copy
import json
import logging
import math
import time
from collections import Counter, defaultdict

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.service.detect.strategy import (
    ExprDetectAlgorithms,
    RangeRatioAlgorithmsCollection,
    SDKPreDetectMixin,
)
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("detect")


class DetectDirect:
    CEIL = "ceil"
    FLOOR = "floor"
    ALL = "all"


class IntelligentDetect(SDKPreDetectMixin, RangeRatioAlgorithmsCollection):
    """
    智能异常检测（动态阈值算法）
    """

    GROUP_PREDICT_FUNC = api.aiops_sdk.kpi_group_predict
    PREDICT_FUNC = api.aiops_sdk.kpi_predict
    SAS_PREDICT_FUNC = api.aiops_sdk.sas_predict

    AUTO_ALERT_LEVEL_MODE = "auto"
    DEFAULT_ALERT_LEVEL = 2

    def generate_sdk_predict_params(self) -> dict:
        return {
            "predict_args": {
                arg_key.lstrip("$"): arg_value for arg_key, arg_value in self.validated_config["args"].items()
            },
            "serving_config": {
                # 从 extra_config 中获取控制参数
                "service_name": self.extra_config.get("service_name") or "default",
                "grey_to_bkfara": self.extra_config.get("grey_to_bkfara", False),
                "enable_week_compare": self.extra_config.get("enable_week_compare", False),
            },
            "extra_data": {
                "history_anomaly": {
                    "source": "backfill",
                    "retention_period": "8d",
                    "backfill_fields": ["anomaly_alert", "extra_info"],
                    "backfill_conditions": [
                        {
                            "field_name": "anomaly_alert",
                            "value": 1,
                        }
                    ],
                },
            },
        }

    def gen_expr(self):
        expr = "is_anomaly > 0"
        yield ExprDetectAlgorithms(
            expr,
            _(
                "{% load unit %}智能模型检测到异常"
                "{% if alert_msg is not None %}, 异常类型: {{ alert_msg }}{% endif %}"
                "{% if anomaly_score is not None %}, 异常分值: {{ anomaly_score }}{% endif %}"
                "{% if previous_point is not None %}, 前一时刻值{{ previous_point.value | auto_unit:unit }}{% endif %}"
            ),
        )

    def detect_records(self, data_points, level):
        anomaly_points = super().detect_records(data_points, level)
        if not data_points:
            return anomaly_points

        query_config = data_points[0].item.query_configs[0]
        if (query_config.get("intelligent_detect") or {}).get("use_sdk") is not True:
            return anomaly_points

        mode = self.validated_config.get("alert_level_mode", "manual")
        try:
            self._report_feature_metrics(mode, len(data_points), len(anomaly_points))
        except Exception as error:
            item = data_points[0].item
            logger.warning(
                "strategy(%s) report dynamic alert level coverage failed: %s",
                item.strategy.id,
                error.__class__.__name__,
            )

        if not anomaly_points or mode != self.AUTO_ALERT_LEVEL_MODE:
            return anomaly_points

        batch_started_at = time.monotonic()
        for anomaly_point in anomaly_points:
            self._set_fallback(anomaly_point, "request_failed")

        item = anomaly_points[0].data_point.item
        request_count = 0
        try:
            request_count = self.apply_auto_alert_level(anomaly_points)
        except Exception as error:
            # SAS 是 KPI 的增量下游，任何异常都不能丢弃已经确认的 KPI 异常点
            logger.warning(
                "strategy(%s) apply SAS alert level failed: %s",
                item.strategy.id,
                error.__class__.__name__,
                exc_info=True,
            )
        finally:
            try:
                self._report_sas_metrics(anomaly_points, request_count, time.monotonic() - batch_started_at)
            except Exception as error:
                logger.warning("strategy(%s) report SAS metrics failed: %s", item.strategy.id, error.__class__.__name__)
        return anomaly_points

    @classmethod
    def score_to_alert_level(cls, score):
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("invalid_score")

        score = float(score)
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("invalid_score")

        fatal_threshold = settings.AIOPS_SAS_FATAL_THRESHOLD
        warning_threshold = settings.AIOPS_SAS_WARNING_THRESHOLD
        if not (
            isinstance(fatal_threshold, (int, float))
            and isinstance(warning_threshold, (int, float))
            and not isinstance(fatal_threshold, bool)
            and not isinstance(warning_threshold, bool)
            and math.isfinite(float(fatal_threshold))
            and math.isfinite(float(warning_threshold))
            and 0 <= float(warning_threshold) < float(fatal_threshold) <= 1
        ):
            raise ValueError("invalid_threshold")

        if score >= float(fatal_threshold):
            return 1
        if score >= float(warning_threshold):
            return 2
        return 3

    @staticmethod
    def project_alert_level(raw_alert_level, alert_levels):
        if type(raw_alert_level) is not int or raw_alert_level not in {1, 2, 3}:
            raise ValueError("invalid_alert_level")
        if not (
            isinstance(alert_levels, list)
            and alert_levels
            and all(type(alert_level) is int and alert_level in {1, 2, 3} for alert_level in alert_levels)
            and len(alert_levels) == len(set(alert_levels))
        ):
            raise ValueError("invalid_alert_levels")
        # 数字越小等级越严重；距离相同时选择更严重的等级。
        return min(alert_levels, key=lambda alert_level: (abs(alert_level - raw_alert_level), alert_level))

    @staticmethod
    def _set_alert_level_message(anomaly_point, message):
        raw_extra_info = anomaly_point.data_point.values.get("extra_info", "")
        try:
            extra_info = (
                json.loads(raw_extra_info) if isinstance(raw_extra_info, str) else copy.deepcopy(raw_extra_info)
            )
            if not isinstance(extra_info, dict):
                extra_info = {}
        except (TypeError, ValueError):
            extra_info = {}

        extra_info["alert_level_msg"] = message
        anomaly_point.data_point.values["extra_info"] = json.dumps(
            extra_info, ensure_ascii=False, separators=(",", ":")
        )

    def _set_fallback(self, anomaly_point, reason):
        self._set_alert_level_message(
            anomaly_point,
            {
                "alert_level": self.DEFAULT_ALERT_LEVEL,
                "severity_score": None,
                "status": "fallback",
                "reason": reason,
            },
        )

    @staticmethod
    def _normalize_timestamp(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(float(value)) or int(value) != value:
            return None
        return int(value)

    def _apply_sas_response(self, anomaly_points, response):
        if not isinstance(response, list):
            for anomaly_point in anomaly_points:
                self._set_fallback(anomaly_point, "invalid_response")
            return

        results_by_timestamp = defaultdict(list)
        for result in response:
            if not isinstance(result, dict):
                continue
            timestamp = self._normalize_timestamp(result.get("timestamp"))
            if timestamp is not None:
                results_by_timestamp[timestamp].append(result)

        for anomaly_point in anomaly_points:
            timestamp = anomaly_point.data_point.timestamp * 1000
            matched_results = results_by_timestamp.get(timestamp, [])
            if not matched_results:
                self._set_fallback(anomaly_point, "missing_result")
                continue
            if len(matched_results) > 1:
                self._set_fallback(anomaly_point, "duplicate_result")
                continue

            score = matched_results[0].get("severity_score")
            try:
                raw_alert_level = self.score_to_alert_level(score)
                alert_level = self.project_alert_level(raw_alert_level, self.validated_config.get("alert_levels"))
            except ValueError as error:
                self._set_fallback(anomaly_point, str(error))
                continue

            self._set_alert_level_message(
                anomaly_point,
                {
                    "alert_level": alert_level,
                    "raw_alert_level": raw_alert_level,
                    "severity_score": float(score),
                    "status": "success",
                },
            )

    @staticmethod
    def _get_alert_level_message(anomaly_point):
        try:
            extra_info = json.loads(anomaly_point.data_point.values["extra_info"])
            message = extra_info.get("alert_level_msg")
            return message if isinstance(message, dict) else {}
        except (KeyError, TypeError, ValueError):
            return {}

    @classmethod
    def _summarize_status(cls, anomaly_points):
        statuses = [cls._get_alert_level_message(point).get("status") for point in anomaly_points]
        success_count = statuses.count("success")
        if statuses and success_count == len(statuses):
            return "success"
        if success_count:
            return "partial"
        return "fallback"

    @staticmethod
    def _report_feature_metrics(mode, input_point_count, anomaly_point_count):
        metrics.AIOPS_DYNAMIC_ALERT_LEVEL_POINT_COUNT.labels(mode=mode, stage="input").inc(input_point_count)
        metrics.AIOPS_DYNAMIC_ALERT_LEVEL_POINT_COUNT.labels(mode=mode, stage="anomaly").inc(anomaly_point_count)

    @classmethod
    def _report_sas_request_metrics(cls, anomaly_points, latency):
        status = cls._summarize_status(anomaly_points)
        metrics.AIOPS_SAS_REQUEST_COUNT.labels(status=status).inc()
        metrics.AIOPS_SAS_REQUEST_LATENCY.labels(status=status).observe(latency)
        metrics.AIOPS_SAS_REQUEST_POINT_COUNT.observe(len(anomaly_points))

    def _report_sas_metrics(self, anomaly_points, request_count, batch_latency):
        result_counter = Counter()
        for anomaly_point in anomaly_points:
            message = self._get_alert_level_message(anomaly_point)
            status = message.get("status", "fallback")
            result_counter[status] += 1
            source = "sas" if status == "success" else "fallback"
            metrics.AIOPS_SAS_ALERT_LEVEL_COUNT.labels(
                source=source, alert_level=str(message.get("alert_level", self.DEFAULT_ALERT_LEVEL))
            ).inc()
            if status == "success":
                metrics.AIOPS_SAS_ALERT_LEVEL_PROJECTION_COUNT.labels(
                    raw_alert_level=str(message["raw_alert_level"]), alert_level=str(message["alert_level"])
                ).inc()
            else:
                metrics.AIOPS_SAS_FALLBACK_COUNT.labels(reason=message["reason"]).inc()

        for status, count in result_counter.items():
            metrics.AIOPS_SAS_RESULT_COUNT.labels(status=status).inc(count)

        batch_status = self._summarize_status(anomaly_points)
        metrics.AIOPS_SAS_BATCH_COUNT.labels(status=batch_status).inc()
        metrics.AIOPS_SAS_BATCH_LATENCY.labels(status=batch_status).observe(batch_latency)
        metrics.AIOPS_SAS_BATCH_POINT_COUNT.observe(len(anomaly_points))
        metrics.AIOPS_SAS_BATCH_REQUEST_COUNT.observe(request_count)

    def apply_auto_alert_level(self, anomaly_points):
        item = anomaly_points[0].data_point.item

        anomaly_groups = {}
        for anomaly_point in anomaly_points:
            dimension_key = anomaly_point.data_point.record_id.rsplit(".", 1)[0]
            if dimension_key not in anomaly_groups:
                anomaly_groups[dimension_key] = {
                    "dimensions": self.generate_dimensions(anomaly_point.data_point),
                    "anomaly_points": [],
                }
            anomaly_groups[dimension_key]["anomaly_points"].append(anomaly_point)

        future_groups = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.AIOPS_SAS_PREDICT_CONCURRENCY) as executor:
            for group in anomaly_groups.values():
                group_points = group["anomaly_points"]
                data = [
                    {
                        "timestamp": point.data_point.timestamp * 1000,
                        "value": point.data_point.value,
                        "is_anomaly": point.data_point.values.get("is_anomaly", 1),
                    }
                    for point in group_points
                ]
                started_at = time.monotonic()
                future = executor.submit(
                    self.SAS_PREDICT_FUNC,
                    data=data,
                    dimensions=group["dimensions"],
                    predict_args={"predict_start_time": min(point["timestamp"] for point in data)},
                    interval=int(item.query_configs[0]["agg_interval"]),
                    extra_data={},
                    serving_config={"pre_service_name": "default", "serving_with_ts_depend": True},
                    bk_tenant_id=item.bk_tenant_id,
                )
                future_groups[future] = (group_points, started_at)

            for future in concurrent.futures.as_completed(future_groups):
                group_points, started_at = future_groups[future]
                try:
                    self._apply_sas_response(group_points, future.result())
                except Exception as error:
                    logger.warning("strategy(%s) SAS predict failed: %s", item.strategy.id, error.__class__.__name__)
                try:
                    self._report_sas_request_metrics(group_points, time.monotonic() - started_at)
                except Exception as error:
                    logger.warning(
                        "strategy(%s) report SAS request metrics failed: %s",
                        item.strategy.id,
                        error.__class__.__name__,
                    )
        return len(future_groups)

    def extra_context(self, context):
        values = getattr(context.data_point, "values", {})
        env = copy.deepcopy(values)
        if "extra_info" in env:
            try:
                env["extra_info"] = json.loads(env["extra_info"])
            except Exception as e:
                logger.info("[IntelligentDetect] get extra context error: %s, origin data: %s", e, env["extra_info"])
        else:
            env["extra_info"] = {}

        if "anomaly_score" in env["extra_info"]:
            env["anomaly_score"] = env["extra_info"]["anomaly_score"]

        if "anomaly_score" in env:
            env["anomaly_score"] = round(env["anomaly_score"], settings.POINT_PRECISION)

        if "alert_msg" in env["extra_info"]:
            env["alert_msg"] = env["extra_info"]["alert_msg"]

        # 获取前一时刻的数据
        env["previous_point"] = self.history_point_fetcher(context.data_point)

        return env

    def get_history_offsets(self, item):
        return [item.query_configs[0]["agg_interval"]]
