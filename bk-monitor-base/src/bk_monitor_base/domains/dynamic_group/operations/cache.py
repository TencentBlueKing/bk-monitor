# pyright: reportArgumentType=false
# pyright: reportImplicitStringConcatenation=false
# pyright: reportUnknownVariableType=false

"""
动态分组Redis缓存管理模块

提供动态分组与实例ID列表关联关系的缓存功能
"""

import json
import logging
from typing import Any

from django_redis import get_redis_connection

from bk_monitor_base.domains.dynamic_group.constants import (
    DYNAMIC_GROUP_CACHE_TTL,
    get_dynamic_group_cache_key,
    get_dynamic_inst_group_cache_key,
)

logger = logging.getLogger(__name__)


def _get_inst_group_ids_from_cache(
    redis_client: Any,
    inst_group_cache_key: str,
    inst_id: int,
) -> set[int]:
    """
    从缓存中获取实例当前所属的分组ID集合

    Args:
        redis_client: Redis客户端
        inst_group_cache_key: 实例分组缓存的hash key
        inst_id: 实例ID

    Returns:
        分组ID集合，如果不存在或解析失败则返回空集合
    """
    old_data: Any = redis_client.hget(inst_group_cache_key, inst_id)
    if not old_data:
        return set()

    try:
        old_group_data: dict[str, Any] = json.loads(old_data)
        return set(old_group_data.get("group_ids", []))
    except (json.JSONDecodeError, TypeError):
        return set()


def _remove_group_from_inst_cache(
    redis_client: Any,
    pipeline: Any,
    inst_group_cache_key: str,
    inst_id: int,
    dynamic_group_id: int,
) -> None:
    """
    从实例的分组缓存中移除指定分组ID

    如果移除后实例还属于其他分组，则更新缓存；
    如果没有其他分组了，则删除该实例的缓存记录。

    Args:
        redis_client: Redis客户端
        pipeline: Redis pipeline对象
        inst_group_cache_key: 实例分组缓存的hash key
        inst_id: 实例ID
        dynamic_group_id: 要移除的分组ID
    """
    group_ids = _get_inst_group_ids_from_cache(redis_client, inst_group_cache_key, inst_id)

    # 移除指定分组ID
    group_ids.discard(dynamic_group_id)

    if group_ids:
        # 还有其他分组，更新数据
        new_data = {"group_ids": list(group_ids)}
        pipeline.hset(
            inst_group_cache_key,
            inst_id,
            json.dumps(new_data, ensure_ascii=False),
        )
    else:
        # 没有其他分组了，删除该实例记录
        pipeline.hdel(inst_group_cache_key, inst_id)


def cache_dynamic_group_member(
    dynamic_group_id: int,
    member_list: list[dict[str, Any]],
    object_model_code: str,
    bk_obj_id: str | None = None,
) -> None:
    """
    缓存动态分组成员信息到Redis

    缓存两种关系：
    1. 分组ID -> 成员列表映射
    2. 实例ID -> 所属分组列表映射

    Args:
        dynamic_group_id: 动态分组ID
        member_list: 成员列表，格式：[{"bk_inst_id": 1, ...}, ...]
        object_model_code: 对象模型代码
        bk_obj_id: CMDB对象ID（可选）

    Example:
        >>> cache_dynamic_group_member(
        ...     dynamic_group_id=123,
        ...     member_list=[{"bk_inst_id": 1, "bk_host_name": "host1"}],
        ...     object_model_code="cw-Host",
        ...     bk_obj_id="host"
        ... )
    """
    try:
        redis_client = get_redis_connection()

        # 1. 缓存分组成员信息：分组ID -> 成员数据
        group_cache_key = get_dynamic_group_cache_key(dynamic_group_id)
        cache_data = {
            "cw_object_model_code": object_model_code,
            "bk_obj_id": bk_obj_id or object_model_code,
            "inst_ids": [member.get("bk_inst_id") for member in member_list if member.get("bk_inst_id")],
            "member_list": member_list,
        }

        redis_client.set(
            group_cache_key,
            json.dumps(cache_data, ensure_ascii=False),
            ex=DYNAMIC_GROUP_CACHE_TTL,
        )

        logger.info(
            "cache_dynamic_group_member: 缓存分组成员成功, "
            f"dynamic_group_id={dynamic_group_id}, "
            f"object_model_code={object_model_code}, "
            f"member_count={len(member_list)}"
        )

        # 2. 缓存实例分组关系：实例ID -> 所属分组列表
        inst_group_cache_key = get_dynamic_inst_group_cache_key(object_model_code)

        # 使用pipeline批量操作，提高性能
        pipeline = redis_client.pipeline()

        for member in member_list:
            inst_id = member.get("bk_inst_id")
            if not inst_id:
                continue

            # 获取实例当前所属的分组列表并添加当前分组
            group_ids = _get_inst_group_ids_from_cache(redis_client, inst_group_cache_key, inst_id)
            group_ids.add(dynamic_group_id)

            # 更新实例的分组列表
            new_data = {"group_ids": list(group_ids)}
            pipeline.hset(
                inst_group_cache_key,
                inst_id,
                json.dumps(new_data, ensure_ascii=False),
            )

        # 执行批量操作
        pipeline.execute()

        logger.info(
            "cache_dynamic_group_member: 缓存实例分组关系成功, "
            f"object_model_code={object_model_code}, "
            f"inst_count={len([m for m in member_list if m.get('bk_inst_id')])}"
        )

    except Exception as e:
        logger.exception(f"cache_dynamic_group_member: 缓存失败, dynamic_group_id={dynamic_group_id}, error={e}")


def delete_dynamic_group_cache(
    dynamic_group_id: int,
    member_list: list[dict[str, Any]] | None = None,
    object_model_code: str | None = None,
) -> None:
    """
    删除动态分组缓存

    Args:
        dynamic_group_id: 动态分组ID
        member_list: 成员列表（用于删除实例分组关系）
        object_model_code: 对象模型代码（用于删除实例分组关系）

    Example:
        >>> delete_dynamic_group_cache(
        ...     dynamic_group_id=123,
        ...     member_list=[{"bk_inst_id": 1}],
        ...     object_model_code="cw-Host"
        ... )
    """
    try:
        redis_client = get_redis_connection()

        # 1. 删除分组成员缓存
        group_cache_key = get_dynamic_group_cache_key(dynamic_group_id)
        redis_client.delete(group_cache_key)

        logger.info(f"delete_dynamic_group_cache: 删除分组缓存成功, dynamic_group_id={dynamic_group_id}")

        # 2. 如果提供了成员列表和对象模型代码，删除实例分组关系
        if member_list and object_model_code:
            inst_group_cache_key = get_dynamic_inst_group_cache_key(object_model_code)

            pipeline = redis_client.pipeline()

            for member in member_list:
                inst_id = member.get("bk_inst_id")
                if not inst_id:
                    continue

                _remove_group_from_inst_cache(redis_client, pipeline, inst_group_cache_key, inst_id, dynamic_group_id)

            pipeline.execute()

            logger.info(
                "delete_dynamic_group_cache: 删除实例分组关系成功, "
                f"object_model_code={object_model_code}, "
                f"inst_count={len([m for m in member_list if m.get('bk_inst_id')])}"
            )

    except Exception as e:
        logger.exception(f"delete_dynamic_group_cache: 删除缓存失败, dynamic_group_id={dynamic_group_id}, error={e}")


def get_dynamic_group_cache(dynamic_group_id: int) -> dict[str, Any] | None:
    """
    从Redis获取动态分组缓存数据

    Args:
        dynamic_group_id: 动态分组ID

    Returns:
        缓存数据字典，如果不存在则返回None

    Example:
        >>> data = get_dynamic_group_cache(123)
        >>> print(data)
        {
            "cw_object_model_code": "cw-Host",
            "bk_obj_id": "host",
            "inst_ids": [1, 2, 3],
            "member_list": [...]
        }
    """
    try:
        redis_client = get_redis_connection()
        group_cache_key = get_dynamic_group_cache_key(dynamic_group_id)

        data: Any = redis_client.get(group_cache_key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.exception(f"get_dynamic_group_cache: 获取缓存失败, dynamic_group_id={dynamic_group_id}, error={e}")
        return None


def get_inst_group_ids(inst_id: int, object_model_code: str) -> list[int]:
    """
    获取实例所属的所有分组ID列表

    Args:
        inst_id: 实例ID
        object_model_code: 对象模型代码

    Returns:
        分组ID列表

    Example:
        >>> group_ids = get_inst_group_ids(1, "cw-Host")
        >>> print(group_ids)
        [123, 456, 789]
    """
    try:
        redis_client = get_redis_connection()
        inst_group_cache_key = get_dynamic_inst_group_cache_key(object_model_code)

        data = redis_client.hget(inst_group_cache_key, inst_id)
        if data:
            group_data = json.loads(data)
            return group_data.get("group_ids", [])
        return []
    except Exception as e:
        logger.exception(
            "get_inst_group_ids: 获取实例分组列表失败, "
            f"inst_id={inst_id}, "
            f"object_model_code={object_model_code}, "
            f"error={e}"
        )
        return []


def batch_delete_inst_group_cache(
    inst_ids: list[int],
    object_model_code: str,
    dynamic_group_id: int,
) -> None:
    """
    批量删除实例的分组关系缓存

    Args:
        inst_ids: 实例ID列表
        object_model_code: 对象模型代码
        dynamic_group_id: 要删除的分组ID

    Example:
        >>> batch_delete_inst_group_cache([1, 2, 3], "cw-Host", 123)
    """
    try:
        redis_client = get_redis_connection()
        inst_group_cache_key = get_dynamic_inst_group_cache_key(object_model_code)

        pipeline = redis_client.pipeline()

        for inst_id in inst_ids:
            _remove_group_from_inst_cache(redis_client, pipeline, inst_group_cache_key, inst_id, dynamic_group_id)

        pipeline.execute()

        logger.info(
            "batch_delete_inst_group_cache: 批量删除实例分组关系成功, "
            f"object_model_code={object_model_code}, "
            f"inst_count={len(inst_ids)}, "
            f"dynamic_group_id={dynamic_group_id}"
        )

    except Exception as e:
        logger.exception(
            "batch_delete_inst_group_cache: 批量删除失败, "
            f"object_model_code={object_model_code}, "
            f"dynamic_group_id={dynamic_group_id}, "
            f"error={e}"
        )
