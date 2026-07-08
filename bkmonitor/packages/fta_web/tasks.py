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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery import shared_task
from django.utils.translation import gettext as _

from bkmonitor.documents.issue import IssueDocument
from bkmonitor.models import ActionConfig, ActionPlugin, AlertAssignGroup, AlertAssignRule
from bkmonitor.models.issue import IssueTapdRelation
from constants.action import ActionPluginType
from constants.issue import IssueStatus
from core.drf_resource import api, resource
from fta_web.constants import QuickSolutionsConfig
from monitor_web.strategies.user_groups import create_default_notice_group

logger = logging.getLogger("celery")

DEFAULT_SOPS_ACTION_PLUGIN_ID = "4"


def get_sops_action_plugin_id():
    plugin_id = (
        ActionPlugin.objects.filter(plugin_key=ActionPluginType.SOPS).values_list("id", flat=True).first()
        or DEFAULT_SOPS_ACTION_PLUGIN_ID
    )
    return str(plugin_id)


def has_builtin_quick_solution_actions(bk_biz_id):
    if ActionConfig.origin_objects.filter(bk_biz_id=bk_biz_id, is_builtin=True).exists():
        return True

    solution_names = {
        str(config["name"]) for config in QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.values() if config.get("name")
    }
    if not solution_names:
        return False

    existing_names = set(
        ActionConfig.origin_objects.filter(
            bk_biz_id=bk_biz_id,
            plugin_id=get_sops_action_plugin_id(),
            is_deleted=False,
            name__in=solution_names,
        ).values_list("name", flat=True)
    )
    return solution_names.issubset(existing_names)


@shared_task(ignore_result=True)
def update_home_statistics():
    # 更新首页的统计数据
    for days in [1, 7, 15, 30]:
        start_time = time.time()
        resource.home.all_biz_statistics.request.refresh(days=days)
        end_time = time.time()
        logger.info("[update_home_statistics] refresh %s days data in %ss", days, end_time - start_time)


@shared_task(ignore_result=True)
def run_init_builtin_action_config(bk_biz_id):
    # 为业务初始化快捷套餐
    # 在当前业务下注册对应的快捷内容
    if has_builtin_quick_solution_actions(bk_biz_id):
        logger.info("[init_builtin_action_config(%s)] builtin config is existed", bk_biz_id)
        return

    try:
        for template_data in [
            QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE,
            QuickSolutionsConfig.IDLE_TEMPLATE,
        ]:
            api.sops.import_project_template(bk_biz_id=bk_biz_id, project_id=bk_biz_id, template_data=template_data)
    except BaseException as error:
        logger.exception("[init_builtin_action_config(%s)] error: %s", bk_biz_id, str(error))
        return

    actions = []

    all_templates = api.sops.get_template_list(bk_biz_id=bk_biz_id)
    for template in all_templates:
        if template["name"] not in QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.values():
            continue
        for config_key, name in QuickSolutionsConfig.QUICK_SOLUTIONS_TEMPLATE_NAMES.items():
            solution_name = QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG.get(config_key, {}).get("name")
            if not solution_name:
                continue
            if (
                name == template["name"]
                and not ActionConfig.objects.filter(name=solution_name, bk_biz_id=bk_biz_id).exists()
            ):
                # 当前模板没有创建快捷套餐，则创建
                action_config = {
                    "is_builtin": True,
                    "name": solution_name,
                    "plugin_id": get_sops_action_plugin_id(),
                    "bk_biz_id": bk_biz_id,
                    "desc": _("系统内置快捷套餐"),
                    "execute_config": {
                        "template_detail": QuickSolutionsConfig.QUICK_SOLUTIONS_CONFIG[config_key]["template_detail"],
                        "template_id": template["id"],
                        "timeout": 600,
                    },
                }
                actions.append(ActionConfig.objects.create(**action_config).name)
                break
    logger.info("[init_builtin_action_config(%s)] finished, create configs %s", bk_biz_id, ",".join(actions))


def run_init_builtin_assign_group(bk_biz_id):
    # 初始化全局告警分派规则
    if AlertAssignGroup.origin_objects.filter(bk_biz_id=bk_biz_id, is_builtin=True).exists():
        # 曾经内置过被删除了，忽略
        return

    user_group_id = create_default_notice_group(bk_biz_id, group_name=_("运维"))
    public_rule_info = dict(
        user_groups=[user_group_id],
        actions=[
            {
                "is_enabled": True,
                "action_type": "notice",
                "upgrade_config": {"is_enabled": False, "user_groups": [], "upgrade_interval": 0},
            }
        ],
        bk_biz_id=bk_biz_id,
        is_enabled=True,
        alert_severity=0,
        additional_tags=[],
    )

    assign_group = AlertAssignGroup.objects.create(
        priority=1, is_builtin=True, name="[内置]第三方告警默认规则组", bk_biz_id=bk_biz_id
    )

    third_alert_rule = {
        "assign_group_id": assign_group.id,
        "conditions": [{"field": "alert.event_source", "value": ["bkmonitor"], "method": "neq", "condition": "and"}],
    }
    third_alert_rule.update(public_rule_info)
    AlertAssignRule.objects.create(**third_alert_rule)

    empty_user_assign_group = AlertAssignGroup.objects.create(
        priority=2, is_builtin=True, name="[内置]通知人为空默认规则组", bk_biz_id=bk_biz_id
    )
    empty_user_assign_rule = {
        "assign_group_id": empty_user_assign_group.id,
        "conditions": [
            {"field": "alert.event_source", "value": ["bkmonitor"], "method": "eq", "condition": "and"},
            {"field": "is_empty_users", "value": ["true"], "method": "eq", "condition": "and"},
        ],
    }
    empty_user_assign_rule.update(public_rule_info)
    AlertAssignRule.objects.create(**empty_user_assign_rule)


# TAPD 已完成状态的关键词匹配
# 英文关键词（匹配 status_value，即 TAPD 状态的英文 key）
_TAPD_COMPLETED_STATUS_EN_KEYWORDS = {"closed", "done", "resolved", "verified"}
# 中文关键词（匹配 display_name，即 TAPD 状态的显示名）
_TAPD_COMPLETED_STATUS_CN_KEYWORDS = {"已关闭", "已实现", "已解决", "已完成", "已验证", "done"}


def _is_tapd_status_completed(status_value: str, status_display_name: str) -> bool:
    """判断 TAPD 单据状态是否为已完成状态

    判断逻辑：
    1. 先判断 status_value（英文 key）是否匹配英文关键词
    2. 再判断 status_display_name（显示名）是否匹配关键词
    3. 两者任一匹配即视为已完成

    Args:
        status_value: TAPD 单据的英文状态值（如 "closed"、"done"）
        status_display_name: TAPD 单据的显示名（如 "已关闭"、"已完成"）

    Returns:
        True 表示该状态属于已完成状态
    """
    if not status_value:
        return False

    # 1. 先判断英文 key
    if status_value.lower() in _TAPD_COMPLETED_STATUS_EN_KEYWORDS:
        return True

    # 2. 再判断显示名称 display_name
    if status_display_name and any(keyword in status_display_name for keyword in _TAPD_COMPLETED_STATUS_CN_KEYWORDS):
        return True

    return False


def _resolve_issue_by_tapd_sync(issue_id: str, bk_biz_id: int) -> dict:
    """TAPD 状态同步触发 Issue 自动流转为已解决

    Args:
        issue_id: Issue ID
        bk_biz_id: 业务 ID

    Returns:
        dict，包含 issue_id、status、resolved_time、update_time 字段（成功时）
        空 dict（跳过或失败时）
    """
    try:
        result = api.issue.resolve(
            bk_biz_id=bk_biz_id,
            issue_id=issue_id,
            operator="system",
        )
        logger.info(
            "Issue auto-resolved by TAPD status sync, issue_id=%s, bk_biz_id=%s",
            issue_id,
            bk_biz_id,
        )
        return result
    except Exception:
        logger.warning(
            "Failed to auto-resolve issue by TAPD sync, issue_id=%s, bk_biz_id=%s",
            issue_id,
            bk_biz_id,
            exc_info=True,
        )
        return {}


def _query_and_check_tapd_status(workspace_id: int, tapd_type: str, relations: list[dict]) -> dict:
    """查询 TAPD 状态并判断需要流转的 Issue

    批量查询指定 workspace_id + tapd_type 下的所有 TAPD 单据状态，
    然后判断哪些 Issue 的 TAPD 状态为已完成，需要流转为已解决。

    Args:
        workspace_id: TAPD 项目 ID
        tapd_type: 单据类型，story 或 bug
        relations: 该分组下的关联记录列表

    Returns:
        dict，包含:
        - checked: int, 检查的记录数
        - skipped: int, 跳过的记录数
        - issues_to_resolve: set[tuple[int, str]], 需要流转的 Issue 集合 {(bk_biz_id, issue_id)}
        - error: str (可选), 错误信息
    """
    from fta_web.issue.resources import SearchTAPDItemsResource

    result = {"checked": 0, "skipped": 0, "issues_to_resolve": set()}
    tapd_ids = [str(rel["tapd_id"]) for rel in relations]

    try:
        # 批量查询 TAPD 单据状态
        tapd_items = SearchTAPDItemsResource._query_tapd_items(
            tapd_type=tapd_type,
            workspace_id=workspace_id,
            id=",".join(tapd_ids),
            limit=len(tapd_ids),
            page=1,
            order="created desc",
            fields="id,status",
        )

        # 构建 tapd_id -> (status, status_display_name) 映射
        tapd_status_map = {
            str(item.get("id")): (item.get("status", ""), item.get("status_display_name", "")) for item in tapd_items
        }

        # 检查每个关联记录
        for rel in relations:
            result["checked"] += 1
            tapd_id = str(rel["tapd_id"])
            tapd_status, status_display_name = tapd_status_map.get(tapd_id, ("", ""))

            if not tapd_status:
                result["skipped"] += 1
                continue

            # 判断 TAPD 状态是否为已完成
            if _is_tapd_status_completed(tapd_status, status_display_name):
                result["issues_to_resolve"].add((rel["bk_biz_id"], rel["issue_id"]))
            else:
                result["skipped"] += 1

    except Exception as e:
        logger.warning(
            "Failed to query TAPD status for sync, workspace_id=%s, tapd_type=%s, tapd_ids=%s",
            workspace_id,
            tapd_type,
            tapd_ids,
            exc_info=True,
        )
        result["error"] = str(e)

    return result


def sync_issues_from_tapd_status() -> dict:
    """定时轮询 TAPD 单据状态，自动同步关联 Issue 的状态

    查询所有 sync_status=True 的关联记录，检查对应 TAPD 单据是否为已完成状态。
    若是，则将关联的 Issue 自动流转为已解决。

    Returns:
        dict，包含处理结果统计：
        - checked: int，检查的关联记录数
        - resolved: int，自动流转为已解决的 Issue 数
        - failed: int，处理失败的记录数
        - skipped: int，跳过的记录数（Issue 已解决或 TAPD 状态未完成）
    """

    stats = {"checked": 0, "resolved": 0, "failed": 0, "skipped": 0}

    # 查询所有 sync_status=True 的关联记录
    sync_relations = list(
        IssueTapdRelation.objects.filter(sync_status=True).values(
            "id", "bk_biz_id", "issue_id", "workspace_id", "tapd_id", "tapd_type"
        )
    )

    if not sync_relations:
        return stats

    # 预过滤：批量查询关联的 Issue 状态，排除已解决的 Issue
    issue_ids = list({rel["issue_id"] for rel in sync_relations})
    resolved_issue_ids: set[str] = set()
    try:
        search = (
            IssueDocument.search(all_indices=True)
            .filter("terms", _id=issue_ids)
            .filter("term", status=IssueStatus.RESOLVED)
            .source(["id", "status"])
        )
        for hit in search:
            resolved_issue_ids.add(hit.meta.id)
    except Exception:
        logger.warning("Failed to batch query Issue status, will proceed without pre-filter", exc_info=True)

    # 过滤掉已解决的 Issue 的关联记录
    filtered_relations = [rel for rel in sync_relations if rel["issue_id"] not in resolved_issue_ids]
    stats["skipped"] += len(sync_relations) - len(filtered_relations)

    if not filtered_relations:
        return stats

    # 按 (workspace_id, tapd_type) 分组，用于批量查询 TAPD 状态
    grouped_relations: dict[tuple[int, str], list[dict]] = {}
    for rel in filtered_relations:
        key = (rel["workspace_id"], rel["tapd_type"])
        grouped_relations.setdefault(key, []).append(rel)

    # 需要处理的 Issue 集合
    issues_to_resolve: set[tuple[int, str]] = set()  # {(bk_biz_id, issue_id)}
    total_checked = 0
    total_skipped = 0

    # 并发查询 TAPD 状态并判断需要流转的 Issue
    with ThreadPoolExecutor(max_workers=min(10, len(grouped_relations))) as executor:
        futures = {
            executor.submit(_query_and_check_tapd_status, ws_id, tapd_type, rels): (ws_id, tapd_type)
            for (ws_id, tapd_type), rels in grouped_relations.items()
        }
        for future in as_completed(futures):
            group_key = futures[future]
            try:
                result = future.result()
                total_checked += result["checked"]
                total_skipped += result["skipped"]
                issues_to_resolve.update(result["issues_to_resolve"])
                if "error" in result:
                    stats["failed"] += len(grouped_relations[group_key])
            except Exception:
                logger.warning("并发查询 TAPD 状态并判断需要流转的 Issue时异常 %s", group_key, exc_info=True)
                stats["failed"] += len(grouped_relations[group_key])

    stats["checked"] = total_checked
    stats["skipped"] += total_skipped

    # 并发处理需要流转的 Issue
    if issues_to_resolve:
        with ThreadPoolExecutor(max_workers=min(10, len(issues_to_resolve))) as executor:
            futures = {
                executor.submit(_resolve_issue_by_tapd_sync, issue_id, bk_biz_id): (bk_biz_id, issue_id)
                for bk_biz_id, issue_id in issues_to_resolve
            }
            for future in as_completed(futures):
                biz_id, i_id = futures[future]
                try:
                    result = future.result()
                    if result:
                        stats["resolved"] += 1
                    else:
                        stats["failed"] += 1
                except Exception:
                    logger.warning(
                        "并发同步Issue状态异常, issue_id=%s, bk_biz_id=%s",
                        i_id,
                        biz_id,
                        exc_info=True,
                    )
                    stats["failed"] += 1

    logger.info(
        "TAPD status sync completed: checked=%d, resolved=%d, failed=%d, skipped=%d",
        stats["checked"],
        stats["resolved"],
        stats["failed"],
        stats["skipped"],
    )

    return stats


@shared_task(ignore_result=True)
def sync_tapd_issue_status():
    """定时同步 TAPD 单据状态到关联的 Issue"""
    start_time = time.time()
    try:
        stats = sync_issues_from_tapd_status()
        elapsed = time.time() - start_time
        logger.info(
            "[sync_tapd_issue_status] completed in %.2fs, stats: %s",
            elapsed,
            stats,
        )
    except Exception as e:
        logger.exception("[sync_tapd_issue_status] failed, error: %s", e)
