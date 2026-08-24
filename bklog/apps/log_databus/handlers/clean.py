"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from math import isfinite

from django.db import transaction
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from apps.exceptions import ValidationError
from apps.log_databus.constants import (
    AsyncStatus,
    CleanTemplateStatus,
    CleanTemplateSyncMessage,
    CleanTemplateSyncStatus,
    EtlConfig,
)
from apps.log_databus.exceptions import (
    CleanTemplateNotExistException,
    CleanTemplateRepeatException,
    CollectorConfigNotExistException,
    EtlPreviewException,
)
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_handler.log import LogCollectorHandler
from apps.log_databus.models import BKDataClean, CleanStash, CleanTemplate, CollectorConfig
from apps.log_databus.tasks.bkdata import sync_clean
from apps.log_databus.utils.bkdata_clean import BKDataCleanUtils
from apps.log_search.constants import IndexSetDataType, LogAccessTypeEnum
from apps.log_search.models import LogIndexSet, LogIndexSetData, Space
from apps.models import model_to_dict
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc


def _is_string_compatible(value) -> bool:
    return not isinstance(value, dict | list)


_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


def _is_integer_in_range(value, minimum: int, maximum: int) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return number.is_finite() and number == number.to_integral_value() and minimum <= number <= maximum


def _is_int_compatible(value) -> bool:
    return _is_integer_in_range(value, _INT32_MIN, _INT32_MAX)


def _is_long_compatible(value) -> bool:
    return _is_integer_in_range(value, _INT64_MIN, _INT64_MAX)


def _is_float_compatible(value) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return isfinite(number)


def _is_object_compatible(value) -> bool:
    return isinstance(value, dict)


def _is_nested_compatible(value) -> bool:
    return isinstance(value, dict | list)


_FIELD_TYPE_VALIDATORS: dict[str, Callable[[object], bool]] = {
    "string": _is_string_compatible,
    "int": _is_int_compatible,
    "long": _is_long_compatible,
    "double": _is_float_compatible,
    "float": _is_float_compatible,
    "object": _is_object_compatible,
    "flattened": _is_object_compatible,
    "nested": _is_nested_compatible,
}


class CleanHandler:
    def __init__(self, collector_config_id):
        self.collector_config_id = collector_config_id
        try:
            self.data = CollectorConfig.objects.get(collector_config_id=self.collector_config_id)
        except CollectorConfig.DoesNotExist:
            raise CollectorConfigNotExistException()

    def refresh(self, raw_data_id, bk_biz_id):
        bkdata_clean_utils = BKDataCleanUtils(raw_data_id=raw_data_id)
        bkdata_clean_utils.update_or_create_clean(
            collector_config_id=self.collector_config_id, bk_biz_id=bk_biz_id, category_id=self.data.category_id
        )
        result_table_names = BKDataClean.objects.filter(raw_data_id=raw_data_id).values_list(
            "result_table_name", flat=True
        )
        if not result_table_names:
            return []
        return result_table_names

    @classmethod
    def sync(cls, bk_biz_id: int, polling: bool):
        """
        to sync clean from bkdata and to create or delete log_index_set
        @param bk_biz_id int biz_id
        @param polling bool is polling request or not
        """
        lock_able = BKDataCleanUtils.lock_sync_clean(bk_biz_id=bk_biz_id)
        if lock_able and polling:
            BKDataCleanUtils.unlock_sync_clean(bk_biz_id=bk_biz_id)
            return AsyncStatus.DONE
        if lock_able and not polling:
            sync_clean.delay(bk_biz_id=bk_biz_id)
        return AsyncStatus.RUNNING


class CleanTemplateHandler:
    SYNC_MAX_WORKERS = 20
    SNAPSHOT_FIELDS = ("clean_type", "etl_params", "etl_fields")

    def __init__(self, clean_template_id=None):
        self.clean_template_id = clean_template_id
        self.data = None
        if clean_template_id:
            try:
                self.data = CleanTemplate.objects.get(clean_template_id=self.clean_template_id)
            except CleanTemplate.DoesNotExist:
                raise CleanTemplateNotExistException(
                    CleanTemplateNotExistException.MESSAGE.format(clean_template_id=clean_template_id)
                )

    @staticmethod
    def get_related_index_set_map(index_set_ids) -> dict[str, list[dict]]:
        """批量查询子索引集所属的索引组，并按子索引集 ID 返回。"""
        index_set_ids = {str(index_set_id) for index_set_id in index_set_ids if index_set_id is not None}
        if not index_set_ids:
            return {}

        relations = list(
            LogIndexSetData.objects.filter(
                result_table_id__in=index_set_ids,
                type=IndexSetDataType.INDEX_SET.value,
            )
            .values("result_table_id", "index_set_id")
            .order_by("index_set_id", "index_id")
        )
        related_index_sets = {
            index_set["index_set_id"]: index_set
            for index_set in LogIndexSet.objects.filter(
                index_set_id__in={relation["index_set_id"] for relation in relations},
                is_group=True,
            ).values("index_set_id", "index_set_name")
        }

        related_index_set_map = {}
        related_index_set_ids_map = {}
        for relation in relations:
            related_index_set = related_index_sets.get(relation["index_set_id"])
            if not related_index_set:
                continue
            child_index_set_id = str(relation["result_table_id"])
            related_index_set_ids = related_index_set_ids_map.setdefault(child_index_set_id, set())
            if related_index_set["index_set_id"] in related_index_set_ids:
                continue
            related_index_set_ids.add(related_index_set["index_set_id"])
            related_index_set_map.setdefault(child_index_set_id, []).append(related_index_set)
        return related_index_set_map

    @staticmethod
    def fill_template_stats(clean_templates):
        clean_templates = list(clean_templates)
        if not clean_templates:
            return clean_templates

        clean_template_ids = [clean_template.clean_template_id for clean_template in clean_templates]
        bk_biz_ids = {clean_template.bk_biz_id for clean_template in clean_templates}
        collector_stats = (
            CollectorConfig.objects.filter(
                clean_template_id__in=clean_template_ids,
                bk_biz_id__in=bk_biz_ids,
                is_active=True,
            )
            .values("clean_template_id", "index_set_id")
            .annotate(total=Count("collector_config_id"))
        )
        active_collector_count_map = {clean_template_id: 0 for clean_template_id in clean_template_ids}
        template_index_set_ids_map = {clean_template_id: set() for clean_template_id in clean_template_ids}
        for stat in collector_stats:
            clean_template_id = stat["clean_template_id"]
            total = stat["total"]
            active_collector_count_map[clean_template_id] += total
            if stat["index_set_id"] is not None:
                template_index_set_ids_map[clean_template_id].add(stat["index_set_id"])

        related_index_set_map = CleanTemplateHandler.get_related_index_set_map(
            {index_set_id for index_set_ids in template_index_set_ids_map.values() for index_set_id in index_set_ids}
        )

        for clean_template in clean_templates:
            etl_fields = clean_template.etl_fields
            if clean_template.status == CleanTemplateStatus.DRAFT.value and clean_template.snapshot:
                etl_fields = clean_template.snapshot.get("etl_fields", etl_fields)
            clean_template.field_count = sum(
                not field.get("is_delete", False) and not field.get("is_built_in", False)
                for field in (etl_fields or [])
            )
            clean_template.active_collector_count = active_collector_count_map[clean_template.clean_template_id]
            clean_template.related_index_set_count = len(
                {
                    related_index_set["index_set_id"]
                    for index_set_id in template_index_set_ids_map[clean_template.clean_template_id]
                    for related_index_set in related_index_set_map.get(str(index_set_id), [])
                }
            )
        return clean_templates

    @staticmethod
    def get_active_collectors_queryset(clean_template_id: int, bk_biz_id: int):
        """查询当前引用模板且在线上生效的采集项。"""
        return CollectorConfig.objects.filter(
            clean_template_id=clean_template_id,
            bk_biz_id=bk_biz_id,
            is_active=True,
        )

    @transaction.atomic
    def create_or_update(self, params: dict):
        if self.data:
            try:
                self.data = CleanTemplate.objects.select_for_update().get(
                    clean_template_id=self.clean_template_id,
                    is_deleted=False,
                )
            except CleanTemplate.DoesNotExist:
                raise CleanTemplateNotExistException(
                    CleanTemplateNotExistException.MESSAGE.format(clean_template_id=self.clean_template_id)
                )

        bk_biz_id = self.data.bk_biz_id if self.data else params["bk_biz_id"]
        model_fields = {
            "name": params["name"],
            "clean_type": params["clean_type"],
            "etl_params": params["etl_params"],
            "etl_fields": params["etl_fields"],
            "bk_biz_id": bk_biz_id,
        }
        if "description" in params:
            model_fields["description"] = params["description"]

        if self._check_clean_template_exist(name=model_fields["name"], bk_biz_id=model_fields["bk_biz_id"]):
            space = Space.objects.get(bk_biz_id=model_fields["bk_biz_id"])
            raise CleanTemplateRepeatException(
                CleanTemplateRepeatException.MESSAGE.format(
                    bk_biz=f"[{space.bk_biz_id}]{space.space_name}",
                    name=model_fields["name"],
                )
            )

        if not self.data:
            clean_template = CleanTemplate.objects.create(
                **model_fields,
                status=CleanTemplateStatus.PUBLISHED.value,
            )
            logger.info(f"create clean template {clean_template.clean_template_id}")
            return model_to_dict(clean_template)

        self.data.name = model_fields["name"]
        if "description" in model_fields:
            self.data.description = model_fields["description"]

        clean_config_changed = any(getattr(self.data, field) != model_fields[field] for field in self.SNAPSHOT_FIELDS)
        should_save_draft = self.data.status == CleanTemplateStatus.DRAFT.value or (
            clean_config_changed
            and CollectorConfig.objects.filter(clean_template_id=self.data.clean_template_id).exists()
        )
        if should_save_draft:
            self.data.snapshot = {field: copy.deepcopy(model_fields[field]) for field in self.SNAPSHOT_FIELDS}
            self.data.status = CleanTemplateStatus.DRAFT.value
        else:
            for field in self.SNAPSHOT_FIELDS:
                setattr(self.data, field, model_fields[field])
            self.data.snapshot = None
            self.data.status = CleanTemplateStatus.PUBLISHED.value
        self.data.save()
        logger.info(f"update clean template {self.data.clean_template_id}, status: {self.data.status}")
        return model_to_dict(self.data)

    def list_collectors(self):
        bk_biz_id = self.data.bk_biz_id
        collectors = list(
            self.get_active_collectors_queryset(self.data.clean_template_id, bk_biz_id)
            .values(
                "collector_config_id",
                "collector_config_name",
                "bk_biz_id",
                "index_set_id",
                "collector_scenario_id",
                "environment",
            )
            .order_by("collector_config_id")
        )
        LogCollectorHandler.fill_container_fields(collectors)
        related_index_set_map = self.get_related_index_set_map({collector["index_set_id"] for collector in collectors})
        return [
            {
                "collector_config_id": collector["collector_config_id"],
                "collector_config_name": collector["collector_config_name"],
                "bk_biz_id": collector["bk_biz_id"],
                "log_access_type": LogAccessTypeEnum.get_log_access_type(
                    scenario_id="",
                    collector_scenario_id=collector["collector_scenario_id"] or "",
                    environment=collector["environment"] or "",
                    container_collector_type=collector.get("container_collector_type", ""),
                ),
                "related_index_set_list": related_index_set_map.get(str(collector["index_set_id"]), []),
            }
            for collector in collectors
        ]

    def destroy(self):
        clean_template_id = self.data.clean_template_id
        with transaction.atomic():
            self.data.delete()
            CollectorConfig.objects.filter(clean_template_id=clean_template_id).update(clean_template_id=None)
            CleanStash.objects.filter(clean_template_id=clean_template_id).update(clean_template_id=None)
        logger.info(f"delete clean template {clean_template_id}")
        return clean_template_id

    def sync_collectors(self, collector_config_ids=None):
        """发布模板草稿，并将正式配置同步到关联采集项。"""
        with transaction.atomic():
            try:
                self.data = CleanTemplate.objects.select_for_update().get(clean_template_id=self.clean_template_id)
            except CleanTemplate.DoesNotExist:
                raise CleanTemplateNotExistException(
                    CleanTemplateNotExistException.MESSAGE.format(clean_template_id=self.clean_template_id)
                )
            for field, value in (self.data.snapshot or {}).items():
                if field in self.SNAPSHOT_FIELDS:
                    setattr(self.data, field, copy.deepcopy(value))
            self.data.snapshot = None
            self.data.status = CleanTemplateStatus.PUBLISHED.value
            self.data.save()

        clean_config = {
            "etl_config": self.data.clean_type,
            "etl_params": copy.deepcopy(self.data.etl_params),
            "fields": copy.deepcopy(self.data.etl_fields),
            "clean_template_id": self.data.clean_template_id,
        }
        collectors = self.get_active_collectors_queryset(
            self.data.clean_template_id,
            self.data.bk_biz_id,
        )
        if collector_config_ids is not None:
            collectors = collectors.filter(collector_config_id__in=collector_config_ids)
        collectors = list(collectors.order_by("collector_config_id"))

        multi_execute_func = MultiExecuteFunc(max_workers=self.SYNC_MAX_WORKERS)
        for collector in collectors:
            multi_execute_func.append(
                result_key=collector.collector_config_id,
                func=self._sync_collector,
                params={
                    "collector": collector,
                    "clean_config": clean_config,
                },
                multi_func_params=True,
            )
        sync_results = multi_execute_func.run()
        results = []
        for collector in collectors:
            result = sync_results.get(collector.collector_config_id)
            if result is None:
                logger.error(
                    "clean template synchronization result is missing, clean_template_id: %s, collector_config_id: %s",
                    self.data.clean_template_id,
                    collector.collector_config_id,
                )
                result = {
                    "id": collector.collector_config_id,
                    "name": collector.collector_config_name,
                    "status": CleanTemplateSyncStatus.FAILED.value,
                    "message": str(CleanTemplateSyncMessage.FAILED.value),
                }
            results.append(result)
        return results

    def _sync_collector(self, collector: CollectorConfig, clean_config: dict):
        result = {
            "id": collector.collector_config_id,
            "name": collector.collector_config_name,
            "status": CleanTemplateSyncStatus.SUCCESS.value,
            "message": str(CleanTemplateSyncMessage.SUCCESS.value),
        }
        try:
            if not CollectorConfig.objects.filter(
                collector_config_id=collector.collector_config_id,
                clean_template_id=self.data.clean_template_id,
                is_active=True,
            ).exists():
                result.update(
                    status=CleanTemplateSyncStatus.FAILED.value,
                    message=str(CleanTemplateSyncMessage.ASSOCIATION_CHANGED.value),
                )
                return result
            handler = CollectorHandler.get_instance(collector_config_id=collector.collector_config_id)
            params = copy.deepcopy(clean_config)
            # 模板批量同步只下发配置，不参与采集项关联关系维护。
            params.pop("clean_template_id", None)
            handler.create_or_update_clean_config(is_update=True, params=params)
            if not CollectorConfig.objects.filter(
                collector_config_id=collector.collector_config_id,
                clean_template_id=self.data.clean_template_id,
                is_active=True,
            ).exists():
                result.update(
                    status=CleanTemplateSyncStatus.FAILED.value,
                    message=str(CleanTemplateSyncMessage.ASSOCIATION_CHANGED.value),
                )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "submit clean template synchronization failed, clean_template_id: %s, collector_config_id: %s",
                self.data.clean_template_id,
                collector.collector_config_id,
            )
            result.update(
                status=CleanTemplateSyncStatus.FAILED.value,
                message=str(CleanTemplateSyncMessage.FAILED.value),
            )
        return result

    def preview(self, data: str):
        """使用模板配置解析日志样例。"""
        # etl_preview 会补充/消费部分参数，不能修改模板中持久化的配置。
        from apps.log_databus.handlers.etl import EtlHandler

        try:
            preview = EtlHandler.etl_preview(
                etl_config=self.data.clean_type,
                etl_params=copy.deepcopy(self.data.etl_params or {}),
                data=data,
                bk_biz_id=self.data.bk_biz_id,
            )
        except (EtlPreviewException, ValidationError) as error:
            # 样例与清洗类型不匹配时，统一返回面向用户的提示；其他异常保持原样抛出。
            raise EtlPreviewException(_("字段提取预览失败，模版与日志样例格式不匹配，请切换模版或手动清洗")) from error

        fields = self._build_preview_fields(preview.get("fields", []))
        normal_count = sum(not field["error_type"] for field in fields)
        total_count = len(fields)
        return {
            "fields": fields,
            "match_rate": round(normal_count * 100 / total_count, 1) if total_count else 100.0,
            "normal_count": normal_count,
            "abnormal_count": total_count - normal_count,
        }

    def _build_preview_fields(self, parsed_fields) -> list:
        if not isinstance(parsed_fields, list):
            parsed_fields = []

        by_name = {field.get("field_name"): field for field in parsed_fields if field.get("field_name") is not None}
        by_index = {field.get("field_index"): field for field in parsed_fields if field.get("field_index") is not None}
        result = []
        for field in self.data.etl_fields or []:
            if field.get("is_built_in") or field.get("is_delete"):
                continue

            item = copy.deepcopy(field)

            if self.data.clean_type == EtlConfig.BK_LOG_DELIMITER:
                parsed_field = by_index.get(field.get("field_index"))
            else:
                parsed_field = by_name.get(field.get("field_name"))

            value = parsed_field.get("value") if parsed_field else None
            item["value"] = value if value is not None else ""
            error_type = self._get_field_error_type(value, field.get("field_type"))
            if error_type == "TYPE_MISMATCH":
                inferred_field_type = self._infer_field_type(value)
            elif error_type == "EMPTY_VALUE":
                inferred_field_type = None
            else:
                inferred_field_type = field.get("field_type")
            item.update(
                {
                    "inferred_field_type": inferred_field_type,
                    "error_type": error_type,
                }
            )
            result.append(item)
        return result

    @staticmethod
    def _infer_field_type(value) -> str:
        if isinstance(value, bool):
            return "string"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, int):
            return "int" if _INT32_MIN <= value <= _INT32_MAX else "long"
        if isinstance(value, float):
            return "double"
        return "string"

    @staticmethod
    def _get_field_error_type(value, field_type: str | None) -> str | None:
        if value is None or value == "":
            return "EMPTY_VALUE"

        validator = _FIELD_TYPE_VALIDATORS.get(field_type)
        if validator and not validator(value):
            return "TYPE_MISMATCH"
        return None

    def _check_clean_template_exist(self, name: str, bk_biz_id: int):
        """
        judge the same bk_biz_id and same name clean_template exist
        """
        qs = CleanTemplate.objects.filter(name=name, bk_biz_id=bk_biz_id)
        if self.data:
            qs = qs.exclude(clean_template_id=self.clean_template_id)
        return qs.exists()
