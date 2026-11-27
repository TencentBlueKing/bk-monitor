"""指标明细/汇总 RT 的声明，以及 Metadata、BKBase 和 Doris 共用的字段投影。"""

import json
import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetricIngestOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metrics: list[str] = Field(min_length=1)
    # 上报 dimension 的 key -> 物理列名，过滤条件使用展开后的列名。
    dimensions: dict[str, str] = Field(default_factory=dict)
    dimension_filters: dict[str, str] = Field(default_factory=dict)
    task_num: int = Field(default=1, gt=0)

    @model_validator(mode="after")
    def check_columns(self) -> Self:
        reserved = {
            "time",
            "timestamp",
            "thedate",
            "dteventtimestamp",
            "dteventtime",
            "localtime",
            "__shard_key__",
            "__unique_key__",
            "__raw_data",
            "root",
            "batch",
            "point",
            "metrics_map",
            "metric",
            "window_end",
            "source_metric",
            "end_ms",
            "metric_name",
            "metric_value",
            "target",
            "source_sample_count",
            "refreshed_at",
        }
        for column in self.dimensions.values():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", column) or column.lower() in reserved:
                raise ValueError(f"展开维度列名重复、保留或非法: {column}")
            reserved.add(column.lower())
        if not self.dimension_filters.keys() <= set(self.labels):
            raise ValueError("dimension_filters 需要使用声明的维度列名")
        return self

    @property
    def labels(self):
        return ["target", *sorted(self.dimensions.values())]

    def clean_transform(self):
        def rule(source, output, kind, **options):
            return {"input_id": source, "output_id": output, "operator": {"type": kind, **options}}

        def equals(field, value):
            return {"BinOp": {"Eq": {"lval": {"Field": field}, "rval": {"Const": value}}}}

        rules = [
            rule("__raw_data", "root", "json_de", error_strategy="drop"),
            rule("root", "batch", "get", key_index=[{"type": "key", "value": "data"}]),
            rule("batch", "point", "iter"),
            rule(
                "point",
                "timestamp",
                "assign",
                key_index="timestamp",
                output_type="long",
                is_time_field=True,
                time_format={"format": "Unix Time Stamp(milliseconds)", "zone": 8},
            ),
            rule("point", "target", "assign", key_index="target", output_type="string", default_value=""),
        ]
        rules.extend(
            rule(
                "point",
                column,
                "assign",
                key_index=f"dimension.{key if key.isidentifier() else json.dumps(key, ensure_ascii=False)}",
                output_type="string",
                default_value="",
            )
            for key, column in self.dimensions.items()
        )
        rules.extend(
            [
                rule("point", "metrics_map", "get", key_index=[{"type": "key", "value": "metrics"}]),
                rule("metrics_map", "metric", "iter"),
                rule("metric", "metric_name", "assign", key_index="key", output_type="string"),
                rule("metric", "metric_value", "assign", key_index="value", output_type="double"),
            ]
        )
        condition = equals("metric_name", self.metrics[0])
        for metric in self.metrics[1:]:
            condition = {"Or": {"lval": condition, "rval": equals("metric_name", metric)}}
        for column, value in self.dimension_filters.items():
            condition = {"And": {"lval": condition, "rval": equals(column, value)}}
        return {"kind": "Clean", "rules": rules, "filter_rules": condition, "error_strategy": "drop"}


class MetricAggregateOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_table_id: str = Field(min_length=1)
    template_key: Literal["sum_without"] = "sum_without"
    without: list[str] = Field(default_factory=list)
    window_minutes: int = Field(default=1, gt=0)
    interval_minutes: int = Field(default=1, gt=0)
    lookback_minutes: int = Field(default=10, gt=0)
    output_prefix: str = ""
    normalize_callee_method: bool = False

    @model_validator(mode="after")
    def check_window(self) -> Self:
        if self.lookback_minutes % self.window_minutes or self.lookback_minutes < self.interval_minutes:
            raise ValueError("回看长度须覆盖调度间隔，并包含整数个窗口")
        return self

    def layout(self, source: MetricIngestOption) -> dict:
        if set(self.without) - set(source.labels):
            raise ValueError("without 包含明细 RT 未声明的维度")
        labels = [label for label in source.labels if label not in self.without]
        if self.normalize_callee_method and "callee_method" not in labels:
            raise ValueError("归一化需要保留 callee_method 维度")
        return {
            "source_table_id": self.source_table_id,
            "labels": labels,
            "window_minutes": self.window_minutes,
            "output_prefix": self.output_prefix,
            "normalize_callee_method": self.normalize_callee_method,
        }


def metric_fields(labels, *, aggregate):
    """两端使用同一份列定义。明细的 timestamp 由 Clean 转为 BKBase 事件时间。"""
    times = [("thedate", "int"), ("dtEventTimeStamp", "long")] if aggregate else [("timestamp", "long")]
    columns = [*times, ("metric_name", "string"), *((name, "string") for name in labels), ("metric_value", "double")]
    if aggregate:
        columns.extend([("source_sample_count", "long"), ("refreshed_at", "string"), ("dtEventTime", "string")])
    dimensions = {"metric_name", *labels}
    return [
        {
            "field_name": name,
            "field_alias": name,
            "field_type": kind,
            "is_dimension": name in dimensions,
            "field_index": index,
        }
        for index, (name, kind) in enumerate(columns)
    ]
