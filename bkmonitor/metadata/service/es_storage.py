"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import datetime
import logging
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from metadata import models

logger = logging.getLogger("metadata")


class ESIndex:
    def __init__(self):
        pass

    def query_es_index(self, table_id_list: list) -> dict:
        """查询结果表对应的es索引"""
        es_objs = models.ESStorage.objects.filter(table_id__in=table_id_list)
        data = {}
        for obj in es_objs:
            item = {"current_index": self._query_current_index(obj)}
            all_index_info = self._query_all_index(obj)
            item["all_index_and_alias"] = self._refine_index_and_aliases(all_index_info)
            item["can_delete_index"] = self._refine_deleted_index(obj, all_index_info)
            data[obj.table_id] = item
        return data

    def _query_current_index(self, es_obj: models.ESStorage) -> dict:
        try:
            return es_obj.current_index_info()
        except Exception as e:
            logger.error("query current index error, %s", e)
            return {}

    def _query_all_index(self, es_obj: models.ESStorage) -> dict:
        try:
            es_client = es_obj.get_client()
            return es_client.indices.get(f"{es_obj.index_name}*")
        except Exception as e:
            logger.error("query all index error, %s", e)
            return {}

    def _refine_index_and_aliases(self, index_info: dict) -> dict:
        """获取索引和别名"""
        data = {}
        for index, detail in index_info.items():
            aliases = list(detail.get("aliases", {}).keys())
            data[index] = aliases
        return data

    def _refine_deleted_index(self, es_obj: models.ESStorage, index_info: dict) -> list:
        """获取可以删除的index

        - 索引的别名已经过期
        - 超过保存时间的索引
        """
        # 可以删除的索引
        can_delete_index = set()
        # 组装参数，获取过期别名的索引
        index_aliases = {}
        for index in index_info:
            index_aliases[index] = {"aliases": index_info[index].get("aliases", {})}
        filter_result = es_obj.group_expired_alias(index_aliases, es_obj.retention)
        for index, aliases in filter_result.items():
            # 回溯的索引不经过正常删除的逻辑删除
            if index.startswith(es_obj.restore_index_prefix):
                continue
            if not aliases["not_expired_alias"]:
                can_delete_index.add(index)

        return list(can_delete_index)


def clone_es_storage_with_cluster(es_storage: models.ESStorage, cluster: models.ClusterInfo) -> models.ESStorage:
    """创建仅用于只读查询的 ESStorage 副本，不修改数据库对象。"""

    runtime_storage = copy.copy(es_storage)
    runtime_storage.storage_cluster_id = cluster.cluster_id
    runtime_storage._cluster = cluster
    runtime_storage.__dict__.pop("es_client", None)
    return runtime_storage


def serialize_es_runtime_value(value: Any) -> Any:
    """将 ES 客户端返回值转换为 Resource 可序列化结构。"""

    if isinstance(value, Mapping):
        return {key: serialize_es_runtime_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [serialize_es_runtime_value(item) for item in value]
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _runtime_index_stats_expression(es_storage: models.ESStorage, index_version: str | None) -> str:
    return es_storage.search_format_v1() if index_version == "v1" else es_storage.search_format_v2()


def _parse_runtime_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized:
            return None
        try:
            return int(float(normalized))
        except ValueError:
            return None
    return None


def _nested_runtime_value(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _first_runtime_value(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _index_setting_value(settings_meta: dict[str, Any], field: str) -> Any:
    settings = settings_meta.get("settings") or {}
    return _first_runtime_value(
        _nested_runtime_value(settings, ("index", field)),
        settings.get(f"index.{field}") if isinstance(settings, Mapping) else None,
    )


def _append_runtime_warning(
    warnings: list[dict[str, Any]], code: str, message: str, error: Exception | None = None
) -> None:
    warning: dict[str, Any] = {"code": code, "message": message}
    if error is not None:
        warning["details"] = {"error": str(error)}
    warnings.append(warning)


def _build_cat_indices_meta(
    es_storage: models.ESStorage,
    index_names: list[str],
    expression: str,
    warnings: list[dict[str, Any]],
    timeout: int | None,
) -> dict[str, dict[str, Any]]:
    if not index_names:
        return {}

    kwargs = {
        "index": expression,
        "h": "index,uuid,health,status,pri,rep,docs.count,docs.deleted,store.size,pri.store.size",
        "format": "json",
        "bytes": "b",
    }
    if timeout is not None:
        kwargs["request_timeout"] = timeout
    try:
        rows = es_storage.es_client.cat.indices(**kwargs)
    except Exception as error:  # pylint: disable=broad-except
        _append_runtime_warning(warnings, "INDEX_CAT_UNAVAILABLE", "ES 索引 cat 信息查询失败", error)
        return {}

    allowed = set(index_names)
    return {
        str(row.get("index")): row
        for row in rows or []
        if isinstance(row, Mapping) and row.get("index") is not None and str(row.get("index")) in allowed
    }


def _build_index_settings_meta(
    es_storage: models.ESStorage,
    index_names: list[str],
    expression: str,
    warnings: list[dict[str, Any]],
    timeout: int | None,
) -> dict[str, dict[str, Any]]:
    if not index_names:
        return {}

    kwargs: dict[str, Any] = {"index": expression}
    if timeout is not None:
        kwargs["request_timeout"] = timeout
    try:
        rows = es_storage.es_client.indices.get_settings(**kwargs)
    except Exception as error:  # pylint: disable=broad-except
        _append_runtime_warning(warnings, "INDEX_SETTINGS_UNAVAILABLE", "ES 索引 settings 查询失败", error)
        return {}

    allowed = set(index_names)
    return {
        str(index_name): meta
        for index_name, meta in (rows or {}).items()
        if isinstance(meta, Mapping) and str(index_name) in allowed
    }


def _build_runtime_index_item(
    index_name: str,
    stats: dict[str, Any],
    cat_meta: dict[str, Any],
    settings_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings_meta = settings_meta or {}
    primary_shards = _parse_runtime_int(
        _first_runtime_value(
            cat_meta.get("pri"),
            cat_meta.get("primary_shards"),
            _index_setting_value(settings_meta, "number_of_shards"),
        )
    )
    replica_factor = _parse_runtime_int(
        _first_runtime_value(
            cat_meta.get("rep"),
            cat_meta.get("replicas"),
            _index_setting_value(settings_meta, "number_of_replicas"),
        )
    )
    replica_shards = (
        primary_shards * replica_factor if primary_shards is not None and replica_factor is not None else None
    )
    total_shards = (
        primary_shards + replica_shards if primary_shards is not None and replica_shards is not None else None
    )
    item = {
        "index": index_name,
        "uuid": _first_runtime_value(
            stats.get("uuid"), cat_meta.get("uuid"), cat_meta.get("id"), _index_setting_value(settings_meta, "uuid")
        ),
        "health": cat_meta.get("health"),
        "status": cat_meta.get("status"),
        "docs_count": _parse_runtime_int(
            _first_runtime_value(
                _nested_runtime_value(stats, ("primaries", "docs", "count")),
                cat_meta.get("docs.count"),
                cat_meta.get("docsCount"),
                cat_meta.get("docs_count"),
                _nested_runtime_value(stats, ("total", "docs", "count")),
            )
        ),
        "docs_deleted": _parse_runtime_int(
            _first_runtime_value(
                _nested_runtime_value(stats, ("primaries", "docs", "deleted")),
                cat_meta.get("docs.deleted"),
                cat_meta.get("docsDeleted"),
                cat_meta.get("docs_deleted"),
                _nested_runtime_value(stats, ("total", "docs", "deleted")),
            )
        ),
        "store_size_bytes": _parse_runtime_int(
            _first_runtime_value(
                _nested_runtime_value(stats, ("total", "store", "size_in_bytes")),
                _nested_runtime_value(stats, ("primaries", "store", "size_in_bytes")),
                cat_meta.get("store.size"),
                cat_meta.get("storeSize"),
                cat_meta.get("store_size"),
            )
        ),
        "primary_store_size_bytes": _parse_runtime_int(
            _first_runtime_value(
                _nested_runtime_value(stats, ("primaries", "store", "size_in_bytes")),
                cat_meta.get("pri.store.size"),
                cat_meta.get("priStoreSize"),
                cat_meta.get("primary_store_size"),
            )
        ),
        "primary_shards": primary_shards,
        "replica_shards": replica_shards,
        "replica_factor": replica_factor,
        "shards": total_shards,
        "creation_date_ms": _parse_runtime_int(_index_setting_value(settings_meta, "creation_date")),
    }
    return {key: value for key, value in item.items() if value is not None}


def _query_expression_stats(
    es_storage: models.ESStorage, expression: str, timeout: int | None
) -> dict[str, dict[str, Any]]:
    kwargs: dict[str, Any] = {"index": expression}
    if timeout is not None:
        kwargs["request_timeout"] = timeout
    response = es_storage.es_client.indices.stats(**kwargs)
    indices = response.get("indices", {}) if isinstance(response, Mapping) else {}
    return dict(indices) if isinstance(indices, Mapping) else {}


def _resolve_index_query(
    es_storage: models.ESStorage,
    index: str | None,
    index_version: str | None = None,
) -> dict[str, Any]:
    if index:
        return {
            "mode": "explicit",
            "need_create_index": bool(es_storage.need_create_index),
            "source": "request_index",
            "expression": index,
        }

    if not es_storage.need_create_index:
        expression = str(es_storage.index_set or "").strip()
        if not expression:
            raise ValueError("need_create_index=False 时 index_set 不能为空")
        return {
            "mode": "external",
            "need_create_index": False,
            "source": "index_set",
            "expression": expression,
        }

    expression = _runtime_index_stats_expression(es_storage, index_version)
    return {
        "mode": "managed",
        "need_create_index": True,
        "source": "generated_table_pattern",
        "expression": expression,
        "index_version": index_version or None,
        "candidates": [es_storage.search_format_v2(), es_storage.search_format_v1()],
    }


def _resolve_index_stats(
    es_storage: models.ESStorage, index: str | None, timeout: int | None
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if index or not es_storage.need_create_index:
        index_query = _resolve_index_query(es_storage, index)
        return _query_expression_stats(es_storage, index_query["expression"], timeout), index_query

    stats_map, index_version = es_storage.get_index_stats(request_timeout=timeout)
    return stats_map, _resolve_index_query(es_storage, index, index_version)


def _filter_runtime_index_names(
    es_storage: models.ESStorage, stats_map: dict[str, dict[str, Any]], index_query: dict[str, Any]
) -> list[str]:
    if index_query["mode"] != "managed" or not index_query.get("index_version"):
        return sorted(str(index_name) for index_name in stats_map)
    index_re = es_storage.index_re_v1 if index_query["index_version"] == "v1" else es_storage.index_re_v2
    return sorted(str(index_name) for index_name in stats_map if index_re.match(str(index_name)))


def _build_indices_overview(
    es_storage: models.ESStorage,
    warnings: list[dict[str, Any]],
    timeout: int | None,
    index: str | None = None,
) -> dict[str, Any]:
    stats_map, index_query = _resolve_index_stats(es_storage, index, timeout)
    index_names = _filter_runtime_index_names(es_storage, stats_map, index_query)
    expression = index_query["expression"]
    cat_meta_map = _build_cat_indices_meta(es_storage, index_names, expression, warnings, timeout)
    settings_meta_map = _build_index_settings_meta(es_storage, index_names, expression, warnings, timeout)
    items = [
        _build_runtime_index_item(
            index_name=index_name,
            stats=stats_map.get(index_name, {}),
            cat_meta=cat_meta_map.get(index_name, {}),
            settings_meta=settings_meta_map.get(index_name, {}),
        )
        for index_name in index_names
    ]
    return {
        "_index_query": index_query,
        "count": len(items),
        "total_docs": sum(item.get("docs_count", 0) for item in items),
        "total_store_size_bytes": sum(item.get("store_size_bytes", 0) for item in items),
        "items": items,
    }


def _parse_managed_alias(es_storage: models.ESStorage, alias_name: str) -> tuple[str, str] | None:
    for alias_type, alias_re in (
        ("write", es_storage.write_alias_re),
        ("write", es_storage.old_write_alias_re),
        ("read", es_storage.read_alias_re),
    ):
        matched = alias_re.fullmatch(alias_name)
        if matched:
            return alias_type, matched.group("datetime")
    return None


def _build_aliases_overview(es_storage: models.ESStorage, raw_aliases: Any) -> dict[str, Any]:
    alias_map: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_aliases, Mapping):
        return {"queried": True, "count": 0, "relation_count": 0, "items": []}

    for index_name, index_meta in raw_aliases.items():
        aliases = index_meta.get("aliases", {}) if isinstance(index_meta, Mapping) else {}
        if not isinstance(aliases, Mapping):
            continue
        for alias_name, alias_meta in aliases.items():
            alias_name = str(alias_name)
            alias_detail = _parse_managed_alias(es_storage, alias_name)
            if alias_detail is None:
                continue
            alias_type, alias_datetime = alias_detail
            item = alias_map.setdefault(
                alias_name,
                {
                    "alias": alias_name,
                    "alias_type": alias_type,
                    "datetime": alias_datetime,
                    "indices": [],
                    "write_index": None,
                },
            )
            item["indices"].append(str(index_name))
            if isinstance(alias_meta, Mapping) and alias_meta.get("is_write_index") is True:
                item["write_index"] = str(index_name)

    items = sorted(alias_map.values(), key=lambda item: item["alias"])
    for item in items:
        item["indices"].sort()
        if item["alias_type"] == "write" and item["write_index"] is None and len(item["indices"]) == 1:
            # ES 旧版本不返回 is_write_index，受管写别名可按唯一关联索引兼容推断。
            item["write_index"] = item["indices"][0]
    return {
        "queried": True,
        "count": len(items),
        "relation_count": sum(len(item["indices"]) for item in items),
        "items": items,
    }


def _query_aliases(es_storage: models.ESStorage, index_names: list[str], timeout: int | None) -> Any:
    if not index_names:
        return {"queried": True, "count": 0, "relation_count": 0, "items": []}
    kwargs: dict[str, Any] = {"index": ",".join(index_names)}
    if timeout is not None:
        kwargs["request_timeout"] = timeout
    return _build_aliases_overview(es_storage, es_storage.get_client().indices.get_alias(**kwargs))


def _resolve_alias_query(
    es_storage: models.ESStorage, index: str | None, timeout: int | None
) -> tuple[dict[str, Any], list[str]]:
    stats_map, index_query = _resolve_index_stats(es_storage, index, timeout)
    return index_query, _filter_runtime_index_names(es_storage, stats_map, index_query)


def _query_mapping(es_storage: models.ESStorage, index: str | None, timeout: int | None) -> Any:
    index_query = _resolve_index_query(es_storage, index)
    kwargs: dict[str, Any] = {"index": index_query["expression"]}
    if timeout is not None:
        kwargs["request_timeout"] = timeout
    return es_storage.get_client().indices.get_mapping(**kwargs)


def _run_runtime_query(
    *,
    name: str,
    es_storage: models.ESStorage,
    bk_tenant_id: str,
    runtime_cluster: models.ClusterInfo,
    query,
    warnings: list[dict[str, Any]],
) -> Any:
    try:
        return query(es_storage)
    except Exception as error:  # pylint: disable=broad-except
        if es_storage.origin_table_id and es_storage.need_create_index:
            physical_storage = models.ESStorage.objects.filter(
                bk_tenant_id=bk_tenant_id, table_id=es_storage.origin_table_id
            ).first()
            if physical_storage is not None:
                try:
                    result = query(clone_es_storage_with_cluster(physical_storage, runtime_cluster))
                    _append_runtime_warning(
                        warnings,
                        "RUNTIME_QUERY_FALLBACK_TO_PHYSICAL",
                        f"{name} 查询虚拟表失败，已回退实体表: table_id={es_storage.table_id}, "
                        f"origin_table_id={es_storage.origin_table_id}",
                        error,
                    )
                    return result
                except Exception as fallback_error:  # pylint: disable=broad-except
                    _append_runtime_warning(
                        warnings,
                        "RUNTIME_QUERY_FAILED",
                        f"{name} 查询失败，虚拟表和实体表回退均不可用: table_id={es_storage.table_id}",
                        fallback_error,
                    )
                    return None
        _append_runtime_warning(
            warnings, "RUNTIME_QUERY_FAILED", f"{name} 查询失败: table_id={es_storage.table_id}", error
        )
        return None


def query_es_storage_runtime(
    *,
    es_storage: models.ESStorage,
    bk_tenant_id: str,
    runtime_cluster: models.ClusterInfo,
    includes: set[str] | None = None,
    index: str | None = None,
    timeout: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """查询指定 ES 集群上的索引、别名及可选 mapping，单项失败不影响其他结果。"""

    includes = {"indices", "aliases"} if includes is None else includes
    runtime_storage = clone_es_storage_with_cluster(es_storage, runtime_cluster)
    warnings: list[dict[str, Any]] = []
    data: dict[str, Any] = {
        "table_id": es_storage.table_id,
        "origin_table_id": es_storage.origin_table_id,
        "table_kind": "virtual" if es_storage.origin_table_id else "physical",
        "index_set": es_storage.index_set,
        "need_create_index": bool(es_storage.need_create_index),
    }
    if "indices" in includes:
        indices = _run_runtime_query(
            name="indices",
            es_storage=runtime_storage,
            bk_tenant_id=bk_tenant_id,
            runtime_cluster=runtime_cluster,
            query=lambda storage: _build_indices_overview(
                storage,
                warnings,
                timeout,
                index,
            ),
            warnings=warnings,
        )
        if isinstance(indices, Mapping):
            data["index_query"] = indices.pop("_index_query", None)
        data["indices"] = indices
    if "aliases" in includes:
        if not es_storage.need_create_index:
            data["aliases"] = {
                "queried": False,
                "reason": "need_create_index_false",
                "count": 0,
                "relation_count": 0,
                "items": [],
            }
        else:
            index_query = data.get("index_query")
            index_names = [item["index"] for item in (data.get("indices") or {}).get("items", [])]
            if not index_query:
                resolved = _run_runtime_query(
                    name="alias index query",
                    es_storage=runtime_storage,
                    bk_tenant_id=bk_tenant_id,
                    runtime_cluster=runtime_cluster,
                    query=lambda storage: _resolve_alias_query(storage, index, timeout),
                    warnings=warnings,
                )
                if resolved:
                    index_query, index_names = resolved
                    data["index_query"] = index_query
                else:
                    data["aliases"] = None
            if index_query:
                data["aliases"] = _run_runtime_query(
                    name="aliases",
                    es_storage=runtime_storage,
                    bk_tenant_id=bk_tenant_id,
                    runtime_cluster=runtime_cluster,
                    query=lambda storage: _query_aliases(storage, index_names, timeout),
                    warnings=warnings,
                )
    if "mapping" in includes:
        data["mapping"] = _run_runtime_query(
            name="mapping",
            es_storage=runtime_storage,
            bk_tenant_id=bk_tenant_id,
            runtime_cluster=runtime_cluster,
            query=lambda storage: _query_mapping(storage, index, timeout),
            warnings=warnings,
        )
    return serialize_es_runtime_value(data), warnings
