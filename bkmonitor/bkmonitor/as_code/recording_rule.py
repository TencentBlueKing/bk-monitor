"""RecordingRule 的 AsCode / 公共 API 入口，不改变 Admin 和后台调度的查询范围。"""

import logging
import os
from collections import defaultdict
from typing import Any

import yaml
from django.db import transaction
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from bkm_space.utils import bk_biz_id_to_space_uid
from metadata import config as metadata_config
from metadata.models import Space
from metadata.models.record_rule.v4.as_code import build_export_entries, dump_rule, parse_config, parse_group
from metadata.models.record_rule.v4.models import CONDITION_FALSE, RecordRuleV4
from metadata.models.record_rule.v4.operator import RecordRuleV4Operator

logger = logging.getLogger(__name__)


def get_space(bk_biz_id: int, space_uid: str | None = None) -> Space:
    canonical_uid = bk_biz_id_to_space_uid(bk_biz_id)
    if space_uid and space_uid != canonical_uid:
        raise ValidationError("bk_biz_id 与 space_uid 不匹配")
    space_type, separator, space_id = canonical_uid.partition("__")
    if not separator:
        raise ValidationError("空间不存在")
    try:
        return Space.objects.get(bk_tenant_id=get_request_tenant_id(), space_type_id=space_type, space_id=space_id)
    except Space.DoesNotExist as error:
        raise ValidationError("当前租户下空间不存在") from error


def active_rules(space: Space):
    return RecordRuleV4.objects.filter(
        bk_tenant_id=space.bk_tenant_id,
        space_type=space.space_type_id,
        space_id=space.space_id,
        is_deleted=False,
    ).select_related("current_spec", "current_spec__latest_resolved", "applied_resolved")


def validate_declaration(declaration: dict[str, Any]) -> None:
    for field in ("name", "data_label"):
        if len(declaration[field]) > 128:
            raise ValueError(f"{field} 最多 128 个字符")
    for index, record in enumerate(declaration["records"]):
        if len(record["metric_name"]) > 128:
            raise ValueError(f"rules[{index}].record 最多 128 个字符")


def parse_group_config(value: dict | str) -> dict[str, Any]:
    try:
        if isinstance(value, str):
            value = yaml.safe_load(value)
        declaration = parse_group(value, source_path="config")
        validate_declaration(declaration)
        return declaration
    except (ValueError, TypeError, yaml.YAMLError) as error:
        raise ValidationError({"config": str(error)}) from error


def save_declaration(
    space: Space,
    declaration: dict[str, Any],
    *,
    rule: RecordRuleV4 | None = None,
    source: str = "api",
    app: str | None = None,
    path: str = "",
) -> RecordRuleV4:
    fields = {key: value for key, value in declaration.items() if key != "source_path"}
    operator = get_request_username(default=source)
    with transaction.atomic(using=metadata_config.DATABASE_CONNECTION_NAME):
        if rule is None:
            rule = RecordRuleV4Operator.declare(
                bk_tenant_id=space.bk_tenant_id,
                space_type=space.space_type_id,
                space_id=space.space_id,
                source=source,
                operator=operator,
                **fields,
            )
        else:
            if fields.pop("name") != rule.name:
                raise ValidationError("规则组名称不可修改")
            rule = RecordRuleV4Operator(rule, source=source, operator=operator).update_declaration(**fields)
        if app is not None:
            rule.app = app
            rule.path = path
            rule.save(update_fields=["app", "path", "updated_at"])
    return rule


def execute_rule(rule: RecordRuleV4, *, source: str = "api") -> dict[str, Any]:
    """执行失败仍保留声明，把执行结果与配置保存结果分开返回。"""
    try:
        succeeded = RecordRuleV4Operator(
            rule, source=source, operator=get_request_username(default=source)
        ).execute_declaration(auto_apply=True)
    except Exception as error:
        logger.exception("RecordingRule execute failed, id: %s", rule.pk)
        return {"succeeded": False, "error": str(error)}
    if succeeded:
        return {"succeeded": True, "error": ""}
    event = rule.events.order_by("-id").first()
    error = (event.message or event.reason) if event else ""
    if not error:
        rule.refresh_from_db()
        error = next(
            (
                condition.get("message") or condition.get("reason")
                for condition in rule.conditions.values()
                if condition.get("status") == CONDITION_FALSE
            ),
            "",
        )
    return {"succeeded": False, "error": error or "解析或下发失败"}


def soft_delete_rule(rule: RecordRuleV4, *, source: str = "api") -> dict[str, Any]:
    with transaction.atomic(using=metadata_config.DATABASE_CONNECTION_NAME):
        rule.is_deleted = True
        rule.save(update_fields=["is_deleted", "updated_at"])
        RecordRuleV4Operator(rule, source=source, operator=get_request_username(default=source)).delete_declaration()
    # 调度器不按 is_deleted 过滤，外部删除失败后仍能继续重试。
    return execute_rule(rule, source=source)


def prepare_import(
    bk_biz_id: int, app: str, configs: dict[str, dict], overwrite: bool
) -> tuple[Space, list[dict[str, Any]], dict[str, str]]:
    space = get_space(bk_biz_id)
    if not app or len(app) > 128:
        raise ValidationError("RecordingRule 的 app 必须为 1 到 128 个字符")
    records = []
    errors = {}
    names = set()
    for path, config in configs.items():
        source_path = f"recording_rule/{path}"
        try:
            declarations = parse_config(config, source_path=source_path)
        except (ValueError, TypeError) as error:
            errors[source_path] = str(error)
            continue
        for index, declaration in enumerate(declarations):
            key = f"{source_path}.groups[{index}]"
            try:
                validate_declaration(declaration)
                if declaration["name"] in names:
                    raise ValueError(f"同一批导入的 group 名称重复: {declaration['name']}")
                names.add(declaration["name"])
            except ValueError as error:
                errors[key] = str(error)
                continue
            records.append({"key": key, "path": path, "declaration": declaration, "rule": None})

    candidates = active_rules(space).filter(name__in=names)
    if not overwrite:
        candidates = candidates.filter(app=app)
    rules_by_name = defaultdict(list)
    for rule in candidates:
        rules_by_name[rule.name].append(rule)
    for record in records:
        name = record["declaration"]["name"]
        matches = rules_by_name[name]
        if len(matches) > 1:
            errors[record["key"]] = f"存在多个同名 RecordingRule，无法确定覆盖对象: {name}"
        elif matches:
            record["rule"] = matches[0]
    return space, records, errors


def import_recording_rules(space: Space, app: str, records: list[dict], *, incremental: bool) -> dict[str, str]:
    errors = {}
    saved_ids = []
    for record in records:
        try:
            rule = save_declaration(
                space,
                record["declaration"],
                rule=record["rule"],
                source="as_code",
                app=app,
                path=record["path"],
            )
            saved_ids.append(rule.pk)
            result = execute_rule(rule, source="as_code")
            if not result["succeeded"]:
                errors[record["key"]] = f"规则 {rule.pk} 已保存，下发失败: {result['error']}"
        except Exception as error:
            logger.exception("RecordingRule import failed, path: %s", record["key"])
            errors[record["key"]] = str(error)
    if errors or incremental:
        return errors
    for rule in active_rules(space).filter(app=app).exclude(pk__in=saved_ids):
        key = f"recording_rule/{rule.path}:{rule.name}"
        try:
            result = soft_delete_rule(rule, source="as_code")
            if not result["succeeded"]:
                errors[key] = f"规则 {rule.pk} 已软删除，Flow 删除失败: {result['error']}"
        except Exception as error:
            logger.exception("RecordingRule cleanup failed, id: %s", rule.pk)
            errors[key] = f"规则 {rule.pk} 删除失败: {error}"
    return errors


def export_recording_rules(
    bk_biz_id: int,
    recording_rule_ids: list[int] | None = None,
    app: str | None = None,
    lock_filename: bool = False,
):
    if recording_rule_ids == []:
        return
    rules = active_rules(get_space(bk_biz_id)).order_by("id")
    if recording_rule_ids is not None:
        rules = rules.filter(pk__in=recording_rule_ids)
    if app is not None:
        rules = rules.filter(app=app)
    rules = list(rules)
    entries = build_export_entries(rules, lock_filename=lock_filename)
    configs = {}
    for rule, entry in zip(rules, entries):
        path = rule.path if rule.path and not lock_filename else entry.filename
        # 合并转换扩展名后重合的来源文件，避免 JSON/YAML 同名文件覆盖丢失 group。
        path = os.path.splitext(path)[0] + ".yaml"
        configs.setdefault(path, {"groups": []})["groups"].append(dump_rule(rule))
    for path, content in configs.items():
        folder, filename = os.path.split(path)
        yield folder, filename, yaml.safe_dump(content, allow_unicode=True, sort_keys=False)
