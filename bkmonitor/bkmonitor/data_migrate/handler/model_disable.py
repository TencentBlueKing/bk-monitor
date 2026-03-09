from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from typing import Any
from collections.abc import Callable

from bkmonitor.data_migrate.handler.base import BaseDirectoryHandler

RecordHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _disable_collect_config_meta(record: dict[str, Any]) -> dict[str, Any]:
    """关闭采集配置，避免导入后直接以下发成功状态继续运行。"""
    fields = record.get("fields")
    if not isinstance(fields, dict):
        return {}

    target_values = {
        "last_operation": "STOP",
        "operation_result": "SUCCESS",
    }
    original_values: dict[str, Any] = {}
    for field_name, target_value in target_values.items():
        if field_name not in fields or fields[field_name] == target_value:
            continue
        original_values[field_name] = deepcopy(fields[field_name])
        fields[field_name] = target_value
    return original_values


def _disable_result_table(record: dict[str, Any]) -> dict[str, Any]:
    """关闭结果表，避免迁移后继续被查询和写入链路使用。"""
    fields = record.get("fields")
    if not isinstance(fields, dict) or "is_enable" not in fields or fields["is_enable"] is False:
        return {}

    original_value = deepcopy(fields["is_enable"])
    fields["is_enable"] = False
    return {"is_enable": original_value}


def _disable_strategy_model(record: dict[str, Any]) -> dict[str, Any]:
    """关闭策略，避免迁移后直接生效。"""
    fields = record.get("fields")
    if not isinstance(fields, dict) or "is_enabled" not in fields or fields["is_enabled"] is False:
        return {}

    original_value = deepcopy(fields["is_enabled"])
    fields["is_enabled"] = False
    return {"is_enabled": original_value}


def _disable_uptimecheck_task(record: dict[str, Any]) -> dict[str, Any]:
    """关闭服务拨测任务，避免迁移后继续运行。"""
    fields = record.get("fields")
    if not isinstance(fields, dict) or "status" not in fields or fields["status"] == "stoped":
        return {}

    original_value = deepcopy(fields["status"])
    fields["status"] = "stoped"
    return {"status": original_value}


MODEL_DISABLE_HANDLERS: dict[str, RecordHandler] = {
    "metadata.datasource": _disable_result_table,
    "metadata.eventgroup": _disable_result_table,
    "metadata.loggroup": _disable_result_table,
    "metadata.resulttable": _disable_result_table,
    "metadata.timeseriesgroup": _disable_result_table,
    "bkmonitor.strategymodel": _disable_strategy_model,
    "monitor.uptimechecktask": _disable_uptimecheck_task,
    "monitor_web.collectconfigmeta": _disable_collect_config_meta,
}


class DisableModelsHandler(BaseDirectoryHandler):
    """
    按模型关闭导出目录中的数据。

    不同模型的关闭方式不同，因此这里统一走模型级处理器映射。
    当前仅支持显式注册过的模型，避免对未知模型做不安全的通用修改。
    """

    name = "disable_models"

    def __init__(self, model_labels: Sequence[str]):
        normalized_model_labels = [
            str(model_label).strip().lower() for model_label in model_labels if str(model_label).strip()
        ]
        unsupported_model_labels = [
            model_label for model_label in normalized_model_labels if model_label not in MODEL_DISABLE_HANDLERS
        ]
        if unsupported_model_labels:
            raise ValueError(f"暂不支持关闭这些模型: {unsupported_model_labels}")
        self.model_labels = list(dict.fromkeys(normalized_model_labels))
        self.recovery_records: list[dict[str, Any]] = []

    def get_manifest_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model_labels": self.model_labels,
            "recovery_record_count": len(self.recovery_records),
        }

    def handle_records(
        self,
        records: list[dict[str, Any]],
        biz_id: int,
        relative_file_path: str,
    ) -> bool:
        changed = False
        enabled_handlers = {model_label: MODEL_DISABLE_HANDLERS[model_label] for model_label in self.model_labels}
        for record in records:
            model_label = str(record.get("model", "")).strip().lower()
            record_handler = enabled_handlers.get(model_label)
            if record_handler is None:
                continue
            original_fields = record_handler(record)
            if not original_fields:
                continue
            self.recovery_records.append(
                {
                    "biz_id": biz_id,
                    "relative_file_path": relative_file_path,
                    "model": record.get("model"),
                    "pk": record.get("pk"),
                    "original_fields": original_fields,
                }
            )
            changed = True
        return changed
