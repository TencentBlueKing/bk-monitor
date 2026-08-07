"""本地资源归属与候选集辅助。

V4 细粒度列表过滤采用「本地候选集 + 批量精确鉴权」；归属真值只读日志平台本地数据，
不在 IAM 运行链路回源监控平台 Metadata。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from apps.iam.handlers.resources import ResourceEnum
from bkm_space.utils import space_uid_to_bk_biz_id


def resolve_indices_bk_biz_id(*, space_uid: str = "", bk_biz_id: Any = None, index_set=None) -> str | None:
    """索引集归属以 LogIndexSet.space_uid 为真值。"""
    if index_set is not None:
        space_uid = getattr(index_set, "space_uid", "") or space_uid
    if space_uid:
        try:
            return str(space_uid_to_bk_biz_id(space_uid))
        except Exception:  # pylint: disable=broad-except
            return None
    if bk_biz_id is not None and str(bk_biz_id) != "":
        return str(bk_biz_id)
    return None


def resolve_collection_bk_biz_id(*, bk_biz_id: Any = None, collector=None) -> str | None:
    """采集项归属以 CollectorConfig.bk_biz_id 为准。"""
    if collector is not None:
        bk_biz_id = getattr(collector, "bk_biz_id", bk_biz_id)
    if bk_biz_id is None or str(bk_biz_id) == "":
        return None
    return str(bk_biz_id)


def resolve_es_source_bk_biz_id(*, bk_biz_id: Any = None, cluster_info: dict | None = None) -> str | None:
    """ES 源归属按 TransferApi 集群 custom_option.bk_biz_id（与现 IAM Provider 契约一致）。"""
    if cluster_info:
        custom_option = (cluster_info.get("cluster_config") or {}).get("custom_option") or {}
        if "bk_biz_id" in custom_option:
            bk_biz_id = custom_option.get("bk_biz_id")
        elif bk_biz_id is None and "bk_biz_id" in cluster_info:
            bk_biz_id = cluster_info.get("bk_biz_id")
    if bk_biz_id is None or str(bk_biz_id) == "":
        return None
    return str(bk_biz_id)


def build_iam_path(bk_biz_id: str | int) -> str:
    return f"/{ResourceEnum.BUSINESS.id},{bk_biz_id}/"


def _normalize_expected_bk_biz_ids(
    expected_bk_biz_id: str | int | None = None,
    expected_bk_biz_ids: Iterable[str | int] | None = None,
) -> set[str]:
    values: list[str | int] = []
    if expected_bk_biz_ids is not None:
        values.extend(expected_bk_biz_ids)
    if expected_bk_biz_id is not None and str(expected_bk_biz_id) != "":
        values.append(expected_bk_biz_id)
    return {str(value) for value in values if value is not None and str(value) != ""}


def resolve_request_bk_biz_id(request) -> str | None:
    """从列表请求参数解析当前空间 bk_biz_id（支持 bk_biz_id / space_uid）。"""
    if request is None:
        return None

    params = None
    for attr in ("query_params", "GET", "data"):
        candidate = getattr(request, attr, None)
        if candidate is not None:
            params = candidate
            break
    if params is None:
        return None

    bk_biz_id = params.get("bk_biz_id")
    if bk_biz_id is not None and str(bk_biz_id) != "":
        return str(bk_biz_id)

    space_uid = params.get("space_uid") or ""
    if not space_uid:
        return None
    try:
        return str(space_uid_to_bk_biz_id(space_uid))
    except Exception:  # pylint: disable=broad-except
        return None


def resource_belongs_to_space(
    *,
    resource_bk_biz_id: str | None,
    expected_bk_biz_id: str | int | None = None,
    expected_bk_biz_ids: Iterable[str | int] | None = None,
    allow_platform: bool = False,
) -> bool:
    """校验资源是否属于目标空间；platform 资源（bk_biz_id=0）可按需豁免。"""
    if resource_bk_biz_id is None:
        return False
    if allow_platform and str(resource_bk_biz_id) == "0":
        return True
    expected = _normalize_expected_bk_biz_ids(expected_bk_biz_id, expected_bk_biz_ids)
    if not expected:
        return False
    return str(resource_bk_biz_id) in expected


def filter_items_by_space_ownership(
    items: list[dict],
    *,
    resolve_bk_biz_id: Callable[[dict], str | None],
    expected_bk_biz_id: str | int | None = None,
    expected_bk_biz_ids: Iterable[str | int] | None = None,
    allow_platform: bool = False,
) -> list[dict]:
    """按本地归属剔除跨空间或无法判定归属的候选。"""
    results = []
    for item in items:
        owner_biz_id = resolve_bk_biz_id(item)
        if resource_belongs_to_space(
            resource_bk_biz_id=owner_biz_id,
            expected_bk_biz_id=expected_bk_biz_id,
            expected_bk_biz_ids=expected_bk_biz_ids,
            allow_platform=allow_platform,
        ):
            results.append(item)
    return results


def filter_nested_items_by_space_ownership(
    result_list: list[dict],
    *,
    resolve_bk_biz_id: Callable[[dict], str | None],
    expected_bk_biz_id: str | int | None = None,
    expected_bk_biz_ids: Iterable[str | int] | None = None,
    allow_platform: bool = False,
    children_field: str = "children",
) -> list[dict]:
    """按本地归属过滤嵌套列表；父节点越权时仍保留归属正确的授权子节点容器。"""
    filtered_result = []
    for item in result_list:
        children = item.get(children_field)
        if isinstance(children, list):
            item[children_field] = filter_nested_items_by_space_ownership(
                children,
                resolve_bk_biz_id=resolve_bk_biz_id,
                expected_bk_biz_id=expected_bk_biz_id,
                expected_bk_biz_ids=expected_bk_biz_ids,
                allow_platform=allow_platform,
                children_field=children_field,
            )

        belongs = resource_belongs_to_space(
            resource_bk_biz_id=resolve_bk_biz_id(item),
            expected_bk_biz_id=expected_bk_biz_id,
            expected_bk_biz_ids=expected_bk_biz_ids,
            allow_platform=allow_platform,
        )
        kept_children = item.get(children_field)
        has_kept_children = isinstance(kept_children, list) and bool(kept_children)
        if belongs or has_kept_children:
            filtered_result.append(item)
    return filtered_result


def filter_nested_items_by_action_permission(
    result_list: list[dict],
    permission_result: dict[str, dict[str, bool]],
    *,
    id_field: str,
    action_id: str,
    children_field: str = "children",
) -> list[dict]:
    """按批量鉴权结果过滤嵌套列表（如索引集树），并回写 permission 注解。

    分组节点本身是 IAM 实体（有 index_set_id）。父节点无权时，若仍有授权子节点，
    保留该分组容器及授权子节点，避免“父无权、子有权”被整棵丢弃。
    """

    def _keep(item: dict) -> bool:
        origin_instance_id = item.get(id_field)
        if not origin_instance_id:
            return True
        return bool(permission_result.get(str(origin_instance_id), {}).get(action_id))

    filtered_result = []
    for item in result_list:
        children = item.get(children_field)
        filtered_children = None
        if isinstance(children, list):
            filtered_children = [child for child in children if _keep(child)]
            item[children_field] = filtered_children

        parent_allowed = _keep(item)
        has_allowed_children = bool(filtered_children)
        if not parent_allowed and not has_allowed_children:
            continue
        filtered_result.append(item)

    annotated_items = []
    for item in filtered_result:
        annotated_items.append(item)
        children = item.get(children_field)
        if isinstance(children, list):
            annotated_items.extend(children)
    for item in annotated_items:
        origin_instance_id = item.get(id_field)
        if not origin_instance_id:
            continue
        instance_id = str(origin_instance_id)
        item.setdefault("permission", {})
        item["permission"].update(permission_result.get(instance_id, {action_id: False}))
    return filtered_result
