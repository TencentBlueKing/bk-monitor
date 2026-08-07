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

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.log_databus.constants import AsyncStatus, CleanTemplateSyncStatus, EtlConfig
from apps.log_databus.exceptions import (
    CleanTemplateNotExistException,
    CleanTemplateRepeatException,
    CleanTemplateSyncingException,
    CollectorConfigNotExistException,
)
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import BKDataClean, CleanTemplate, CollectorConfig
from apps.log_databus.tasks.bkdata import sync_clean
from apps.log_databus.utils.bkdata_clean import BKDataCleanUtils
from apps.log_search.models import Space
from apps.models import model_to_dict
from apps.utils.lock import RedisLock
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc


def _is_string_compatible(value) -> bool:
    return not isinstance(value, dict | list)


def _is_integer_compatible(value) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return float(value).is_integer()
    except (TypeError, ValueError, OverflowError):
        return False


def _is_float_compatible(value) -> bool:
    if isinstance(value, bool):
        return False
    try:
        float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return True


def _is_object_compatible(value) -> bool:
    return isinstance(value, dict)


def _is_nested_compatible(value) -> bool:
    return isinstance(value, dict | list)


_FIELD_TYPE_VALIDATORS: dict[str, Callable[[object], bool]] = {
    "string": _is_string_compatible,
    "int": _is_integer_compatible,
    "long": _is_integer_compatible,
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
    SYNC_LOCK_TTL = getattr(settings, "CLEAN_TEMPLATE_SYNC_LOCK_TTL", 30 * 60)
    SYNC_MAX_WORKERS = getattr(settings, "CLEAN_TEMPLATE_SYNC_MAX_WORKERS", 5)

    def __init__(self, clean_template_id=None, bk_biz_id=None):
        self.clean_template_id = clean_template_id
        self.bk_biz_id = bk_biz_id
        self.data = None
        if clean_template_id:
            try:
                self.data = self._get_template_queryset().get(clean_template_id=self.clean_template_id)
            except CleanTemplate.DoesNotExist:
                raise CleanTemplateNotExistException(
                    CleanTemplateNotExistException.MESSAGE.format(clean_template_id=clean_template_id)
                )

    @staticmethod
    def fill_template_stats(clean_templates):
        clean_templates = list(clean_templates)
        if not clean_templates:
            return clean_templates

        clean_template_ids = [clean_template.clean_template_id for clean_template in clean_templates]
        bk_biz_ids = {clean_template.bk_biz_id for clean_template in clean_templates}
        active_collector_count_map = dict(
            CollectorConfig.objects.filter(
                clean_template_id__in=clean_template_ids,
                bk_biz_id__in=bk_biz_ids,
                is_active=True,
            )
            .values("clean_template_id")
            .annotate(total=Count("collector_config_id"))
            .values_list("clean_template_id", "total")
        )
        for clean_template in clean_templates:
            clean_template.field_count = sum(
                not field.get("is_delete", False) and not field.get("is_built_in", False)
                for field in (clean_template.etl_fields or [])
            )
            clean_template.active_collector_count = active_collector_count_map.get(
                clean_template.clean_template_id,
                0,
            )
        return clean_templates

    def _get_template_queryset(self):
        queryset = CleanTemplate.objects
        if self.bk_biz_id is not None:
            queryset = queryset.filter(bk_biz_id=self.bk_biz_id)
        return queryset

    @staticmethod
    def get_active_collectors_queryset(clean_template_id: int, bk_biz_id: int):
        """查询当前引用模板且在线上生效的采集项。"""
        return CollectorConfig.objects.filter(
            clean_template_id=clean_template_id,
            bk_biz_id=bk_biz_id,
            is_active=True,
        )

    @classmethod
    def get_collectors_to_sync_queryset(cls, clean_template_id: int, bk_biz_id: int, config_version: int):
        """查询同步失败、未同步或模板版本落后的采集项。"""
        return cls.get_active_collectors_queryset(clean_template_id, bk_biz_id).filter(
            Q(clean_template_sync_status=CleanTemplateSyncStatus.FAILED.value)
            | Q(clean_template_version__isnull=True)
            | Q(clean_template_version__lt=config_version)
        )

    def _refresh_template(self):
        try:
            self.data = self._get_template_queryset().get(clean_template_id=self.clean_template_id)
        except CleanTemplate.DoesNotExist:
            raise CleanTemplateNotExistException(
                CleanTemplateNotExistException.MESSAGE.format(clean_template_id=self.clean_template_id)
            )

    def _acquire_operation_lock(self):
        lock = RedisLock(f"clean_template_sync_{self.clean_template_id}", ttl=self.SYNC_LOCK_TTL)
        if not lock.acquire(_wait=0.1):
            raise CleanTemplateSyncingException(
                CleanTemplateSyncingException.MESSAGE.format(clean_template_id=self.clean_template_id)
            )
        return lock

    @staticmethod
    def _serialize_template(clean_template):
        data = model_to_dict(clean_template)
        data.pop("visible_type", None)
        data.pop("visible_bk_biz_id", None)
        return data

    def create_or_update(self, params: dict):
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
            clean_template = CleanTemplate.objects.create(**model_fields)
            logger.info(f"create clean template {clean_template.clean_template_id}")
            return self._serialize_template(clean_template)

        lock = self._acquire_operation_lock()
        try:
            self._refresh_template()
            clean_config_changed = any(
                getattr(self.data, field) != model_fields[field] for field in ("clean_type", "etl_params", "etl_fields")
            )
            for key, value in model_fields.items():
                setattr(self.data, key, value)
            if clean_config_changed:
                self.data.config_version = F("config_version") + 1
            self.data.save()
            if clean_config_changed:
                self.data.refresh_from_db()
            logger.info(f"update clean template {self.data.clean_template_id}")
            return self._serialize_template(self.data)
        finally:
            lock.release()

    def list_collectors(self):
        bk_biz_id = self.data.bk_biz_id
        collectors = list(
            self.get_active_collectors_queryset(self.data.clean_template_id, bk_biz_id)
            .values(
                "collector_config_id",
                "collector_config_name",
                "bk_biz_id",
                "clean_template_version",
                "clean_template_sync_status",
                "clean_template_sync_at",
                "clean_template_sync_message",
            )
            .order_by("collector_config_id")
        )
        space_names = dict(
            Space.objects.filter(bk_biz_id__in={collector["bk_biz_id"] for collector in collectors}).values_list(
                "bk_biz_id", "space_name"
            )
        )
        return [
            {
                **collector,
                "bk_biz_name": space_names.get(collector["bk_biz_id"], str(collector["bk_biz_id"])),
                "clean_template_config_version": self.data.config_version,
                "is_outdated": (
                    collector["clean_template_sync_status"] == CleanTemplateSyncStatus.FAILED.value
                    or collector["clean_template_version"] is None
                    or collector["clean_template_version"] < self.data.config_version
                ),
            }
            for collector in collectors
        ]

    def destroy(self):
        lock = self._acquire_operation_lock()
        try:
            self._refresh_template()
            clean_template_id = self.data.clean_template_id
            with transaction.atomic():
                self.data.delete()
                CollectorConfig.objects.filter(clean_template_id=clean_template_id).update(
                    clean_template_id=None,
                    clean_template_version=None,
                    clean_template_sync_status=None,
                    clean_template_sync_at=None,
                    clean_template_sync_message="",
                )
            logger.info(f"delete clean template {clean_template_id}")
            return clean_template_id
        finally:
            lock.release()

    def sync_collectors(self, collector_config_ids=None):
        lock = self._acquire_operation_lock()
        try:
            self._refresh_template()
            return self._sync_collectors(collector_config_ids=collector_config_ids)
        finally:
            lock.release()

    def _sync_collectors(self, collector_config_ids=None):
        template_version = self.data.config_version
        clean_config = {
            "etl_config": self.data.clean_type,
            "etl_params": copy.deepcopy(self.data.etl_params),
            "fields": copy.deepcopy(self.data.etl_fields),
            "clean_template_id": self.data.clean_template_id,
        }
        collectors = self.get_collectors_to_sync_queryset(
            self.data.clean_template_id,
            self.data.bk_biz_id,
            template_version,
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
                    "template_version": template_version,
                    "clean_config": clean_config,
                },
                multi_func_params=True,
            )
        sync_results = multi_execute_func.run(return_exception=True)
        results = []
        for collector in collectors:
            result = sync_results.get(collector.collector_config_id)
            if result is None:
                continue
            if isinstance(result, Exception):
                logger.error(
                    "sync clean template raised an unexpected exception, clean_template_id: %s, "
                    "collector_config_id: %s, error: %s",
                    self.data.clean_template_id,
                    collector.collector_config_id,
                    result,
                )
                result = {
                    "id": collector.collector_config_id,
                    "name": collector.collector_config_name,
                    "status": CleanTemplateSyncStatus.FAILED.value,
                    "description": f"Failed to sync clean template, reason: {result}",
                }
            results.append(result)
        return results

    def _sync_collector(self, collector: CollectorConfig, template_version: int, clean_config: dict):
        result = {
            "id": collector.collector_config_id,
            "name": collector.collector_config_name,
            "status": CleanTemplateSyncStatus.SUCCESS.value,
            "description": "Sync clean template successfully",
        }
        try:
            updated = CollectorConfig.objects.filter(
                collector_config_id=collector.collector_config_id,
                clean_template_id=self.data.clean_template_id,
            ).update(
                clean_template_sync_status=CleanTemplateSyncStatus.RUNNING.value,
                clean_template_sync_message="",
            )
            if not updated:
                return None
            handler = CollectorHandler.get_instance(collector_config_id=collector.collector_config_id)
            handler.create_or_update_clean_config(
                is_update=True,
                params=copy.deepcopy(clean_config),
                sync_modify_result_table=True,
            )
            CollectorConfig.objects.filter(
                collector_config_id=collector.collector_config_id,
                clean_template_id=self.data.clean_template_id,
            ).update(
                clean_template_version=template_version,
                clean_template_sync_status=CleanTemplateSyncStatus.SUCCESS.value,
                clean_template_sync_at=timezone.now(),
                clean_template_sync_message="",
            )
        except Exception as error:  # pylint: disable=broad-except
            logger.exception(
                "sync clean template failed, clean_template_id: %s, collector_config_id: %s",
                self.data.clean_template_id,
                collector.collector_config_id,
            )
            result.update(
                {
                    "status": CleanTemplateSyncStatus.FAILED.value,
                    "description": f"Failed to sync clean template, reason: {error}",
                }
            )
            CollectorConfig.objects.filter(
                collector_config_id=collector.collector_config_id,
                clean_template_id=self.data.clean_template_id,
            ).update(
                clean_template_sync_status=CleanTemplateSyncStatus.FAILED.value,
                clean_template_sync_at=timezone.now(),
                clean_template_sync_message=str(error),
            )
        return result

    def preview(self, data: str):
        """使用模板配置解析日志样例。"""
        # etl_preview 会补充/消费部分参数，不能修改模板中持久化的配置。
        from apps.log_databus.handlers.etl import EtlHandler

        preview = EtlHandler.etl_preview(
            etl_config=self.data.clean_type,
            etl_params=copy.deepcopy(self.data.etl_params or {}),
            data=data,
            bk_biz_id=self.data.bk_biz_id,
        )
        fields = self._build_preview_fields(preview.get("fields", []))
        normal_count = sum(field["status"] == "NORMAL" for field in fields)
        total_count = len(fields)
        return {
            "clean_template_id": self.data.clean_template_id,
            "etl_config": self.data.clean_type,
            "data": data,
            "fields": fields,
            "match_rate": round(normal_count * 100 / total_count, 1) if total_count else 100.0,
            "normal_count": normal_count,
            "abnormal_count": total_count - normal_count,
        }

    def _build_preview_fields(self, parsed_fields) -> list:
        if self.data.clean_type == EtlConfig.BK_LOG_TEXT and isinstance(parsed_fields, str):
            parsed_fields = [{"field_name": "log", "value": parsed_fields}]
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
                    "status": "ABNORMAL" if error_type else "NORMAL",
                    "error_type": error_type,
                    "error_message": self._get_field_error_message(error_type),
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
            return "long" if value > 2**31 - 1 else "int"
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

    @staticmethod
    def _get_field_error_message(error_type: str | None) -> str:
        return {
            "EMPTY_VALUE": "Field value is empty or the field was not extracted",
            "TYPE_MISMATCH": "Field value does not match the configured type",
        }.get(error_type, "")

    def _check_clean_template_exist(self, name: str, bk_biz_id: int):
        """
        judge the same bk_biz_id and same name clean_template exist
        """
        qs = CleanTemplate.objects.filter(name=name, bk_biz_id=bk_biz_id)
        if self.data:
            qs = qs.exclude(clean_template_id=self.clean_template_id)
        return qs.exists()
