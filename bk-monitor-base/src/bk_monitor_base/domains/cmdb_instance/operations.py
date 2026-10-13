# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
import logging
import math
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, TypeVar, cast

from elasticsearch_dsl.response import Response

from .agent_status import (
    enrich_host_instances_with_agent_status as enrich_host_instances_with_agent_status_impl,
)
from .agent_status import get_host_agent_status_map as get_host_agent_status_map_impl
from .models import CMDBInstance, CMDBInstRelate, CMDBObjRelate

logger = logging.getLogger(__name__)

T = TypeVar("T")


def get_host_agent_status_map(
    bk_tenant_id: str,
    hosts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """批量查询主机 Agent 状态。"""
    return get_host_agent_status_map_impl(bk_tenant_id=bk_tenant_id, hosts=hosts)


def enrich_host_instances_with_agent_status(
    bk_tenant_id: str,
    host_instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """为主机实例补充 Agent 状态字段。"""
    return enrich_host_instances_with_agent_status_impl(
        bk_tenant_id=bk_tenant_id,
        host_instances=host_instances,
    )


def refresh_host_agent_status(
    bk_tenant_id: str,
    bk_host_ids: list[int] | None = None,
    batch_size: int = 500,
) -> int:
    """刷新主机索引中的 Agent 状态字段。"""
    query: dict[str, Any] | None = None
    if bk_host_ids:
        query = {"bk_host_id": bk_host_ids}

    host_instances = search_all_instances(
        bk_obj_id="host",
        bk_tenant_id=bk_tenant_id,
        query=query,
        fields=["bk_host_id", "bk_host_innerip", "bk_cloud_id", "bk_agent_id", "bk_biz_id", "bk_biz_name"],
        batch_size=batch_size,
        ignore_partial_error=True,
    )
    if not host_instances:
        return 0

    refreshed_instances = enrich_host_instances_with_agent_status(
        bk_tenant_id=bk_tenant_id,
        host_instances=host_instances,
    )
    CMDBInstance.bulk_update_or_create("host", refreshed_instances)
    return len(refreshed_instances)


def _paginate(
    search_func: Callable[..., tuple[int, list[T]]],
    batch_size: int,
    **search_kwargs: Any,
) -> Iterator[list[T]]:
    """通用分页迭代器。

    用于封装分页查询的通用逻辑，避免重复的 while True 循环代码。

    Args:
        search_func: 搜索函数，需返回 (total, items) 元组
        batch_size: 每批次大小
        **search_kwargs: 传递给搜索函数的参数

    Yields:
        每批次的结果列表

    Example:
        >>> # 内部使用示例
        >>> for batch in _paginate(search_instances, batch_size=100, bk_obj_id="host"):
        ...     process_batch(batch)
    """
    page = 1

    while True:
        _, items = search_func(**search_kwargs, page=page, size=batch_size)

        # 如果本批次没有数据，停止迭代
        if not items:
            break

        # yield 整批结果
        yield items

        # 如果本批次数据少于batch_size，说明已经是最后一批
        if len(items) < batch_size:
            break

        page += 1


def _build_search_kwargs(
    bk_obj_id: str | None = None,
    bk_inst_ids: list[int] | None = None,
    bk_biz_id: str | None = None,
    bk_biz_ids: list[str] | None = None,
    bk_tenant_id: str | None = None,
    dynamic_group_id: str | None = None,
    cw_object_model_code: str | None = None,
    cw_object_model_inst_id: str | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建查询参数字典（内部辅助函数）。

    将常用参数合并到 query 字典中，避免重复代码。
    """
    query_dict = query.copy() if query else {}

    # 添加内置查询条件
    if bk_obj_id:
        query_dict["bk_obj_id"] = bk_obj_id
    if bk_inst_ids:
        query_dict["bk_inst_id"] = bk_inst_ids
    if bk_biz_id:
        query_dict["bk_biz_id"] = bk_biz_id
    if bk_biz_ids:
        query_dict["bk_biz_id"] = bk_biz_ids
    if bk_tenant_id:
        query_dict["bk_tenant_id"] = bk_tenant_id
    if dynamic_group_id:
        query_dict["dynamic_group_id"] = dynamic_group_id
    if cw_object_model_code:
        query_dict["cw_object_model_code"] = cw_object_model_code
    if cw_object_model_inst_id:
        query_dict["cw_object_model_inst_id"] = cw_object_model_inst_id

    return query_dict


def search_instances(
    bk_obj_id: str | None = None,
    bk_inst_ids: list[int] | None = None,
    bk_biz_id: str | None = None,
    bk_biz_ids: list[str] | None = None,
    bk_tenant_id: str | None = None,
    dynamic_group_id: str | None = None,
    cw_object_model_code: str | None = None,
    cw_object_model_inst_id: str | None = None,
    query: dict[str, Any] | None = None,
    search: dict[str, str] | None = None,
    page: int | None = None,
    size: int | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """搜索CMDB实例。

    支持多种查询条件组合，包括精确匹配、模糊搜索、分页和排序等功能。
    可以查询任意CMDB字段，如主机的IP地址、操作系统类型、状态等。

    Args:
        bk_obj_id: CMDB模型ID，如"host"、"module"等
        bk_inst_ids: 实例ID列表，用于批量查询特定实例
        bk_biz_id: 业务ID，用于过滤特定业务下的实例
        bk_biz_ids: 业务ID列表，用于查询多个业务的实例
        bk_tenant_id: 租户ID，用于过滤特定租户下的实例
        dynamic_group_id: 动态分组ID，用于查询动态分组中的实例
        cw_object_model_code: 对象模型代码，用于查询特定对象模型的实例
        cw_object_model_inst_id: 对象模型实例ID，用于查询特定对象模型实例
        query: 精确匹配参数，支持查询任意CMDB字段。
            格式：{"field_name": value} 或 {"field_name": [value1, value2]}
            示例：{"bk_host_innerip": "192.168.1.1"} 或 {"bk_os_type": ["Linux", "Windows"]}
        search: 模糊匹配参数，支持对任意字段进行模糊搜索。
            格式：{"field_name": "search_text"}
            示例：{"bk_host_name": "prod"}
        page: 页码，从1开始
        size: 每页大小
        sort: 排序字段，如"-create_time"表示按create_time降序，"create_time"表示升序
        fields: 返回字段列表，用于指定需要返回的字段

    Returns:
        元组(总数, 实例列表)，其中总数为符合条件的实例总数，实例列表为当前页的实例数据

    Example:
        >>> # 查询业务ID为2的所有主机实例
        >>> total, instances = search_instances(bk_obj_id="host", bk_biz_id="2")
        >>> print(f"找到 {total} 个主机")

        >>> # 根据IP地址查询主机
        >>> total, instances = search_instances(
        ...     bk_obj_id="host",
        ...     query={"bk_host_innerip": "192.168.1.1"}
        ... )

        >>> # 查询多个IP地址的主机
        >>> total, instances = search_instances(
        ...     bk_obj_id="host",
        ...     query={"bk_host_innerip": ["192.168.1.1", "192.168.1.2"]}
        ... )

        >>> # 根据操作系统类型和状态查询
        >>> total, instances = search_instances(
        ...     bk_obj_id="host",
        ...     query={"bk_os_type": "Linux", "bk_state": "running"}
        ... )

        >>> # 使用模糊搜索查询主机名包含"prod"的主机
        >>> total, instances = search_instances(
        ...     bk_obj_id="host",
        ...     search={"bk_host_name": "prod"}
        ... )

        >>> # 组合查询：业务ID + IP地址 + 模糊搜索主机名
        >>> total, instances = search_instances(
        ...     bk_obj_id="host",
        ...     bk_biz_id="2",
        ...     query={"bk_cloud_id": 0},
        ...     search={"bk_host_name": "web"}
        ... )

        >>> # 分页查询并按创建时间降序排列
        >>> total, instances = search_instances(
        ...     bk_obj_id="host",
        ...     page=1,
        ...     size=20,
        ...     sort="-create_time"
        ... )

        >>> # 查询特定对象模型的实例
        >>> total, instances = search_instances(
        ...     cw_object_model_code="custom_model",
        ...     cw_object_model_inst_id="inst_001"
        ... )

        >>> # 只返回指定字段
        >>> total, instances = search_instances(
        ...     bk_obj_id="host",
        ...     query={"bk_os_type": "Linux"},
        ...     fields=["bk_host_id", "bk_host_innerip", "bk_host_name"]
        ... )
    """
    query_dict = _build_search_kwargs(
        bk_obj_id=bk_obj_id,
        bk_inst_ids=bk_inst_ids,
        bk_biz_id=bk_biz_id,
        bk_biz_ids=bk_biz_ids,
        bk_tenant_id=bk_tenant_id,
        dynamic_group_id=dynamic_group_id,
        cw_object_model_code=cw_object_model_code,
        cw_object_model_inst_id=cw_object_model_inst_id,
        query=query,
    )

    s = CMDBInstance.get_search(
        query=query_dict,
        search=search,
        page=page,
        size=size,
        sort=sort,
        fields=fields,
    )

    response = s.execute()
    total = response.hits.total.value if hasattr(response.hits.total, "value") else response.hits.total

    instances = [hit.to_dict() for hit in response.hits]
    return total, instances


def search_instances_advanced(
    bk_obj_id: str | None = None,
    bk_biz_id: str | None = None,
    bk_tenant_id: str | None = None,
    cw_object_model_code: str | None = None,
    cw_object_model_inst_id: str | None = None,
    query: dict[str, Any] | None = None,
    search: dict[str, str] | None = None,
    or_query: dict[str, Any] | None = None,
    exclude_query: dict[str, Any] | None = None,
    exclude_search: dict[str, str] | None = None,
    time_range: dict[str, Any] | None = None,
    global_search: dict[str, Any] | None = None,
    page: int | None = None,
    size: int | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """高级实例查询（支持OR、排除、时间范围、全局搜索等）。

    提供比 search_instances 更强大的查询能力，适用于复杂查询场景。

    Args:
        bk_obj_id: CMDB模型ID
        bk_biz_id: 业务ID
        bk_tenant_id: 租户ID
        cw_object_model_code: 对象模型代码
        cw_object_model_inst_id: 对象模型实例ID
        query: 精确匹配（AND逻辑），格式：{"field": value} 或 {"field": [value1, value2]}
        search: 模糊搜索（AND逻辑），格式：{"field": "keyword"}
        or_query: OR查询，格式：{"field": [value1, value2]}，表示 field=value1 OR field=value2
        exclude_query: 排除查询，格式：{"field": value} 或 {"field": [value1, value2]}
        exclude_search: 排除模糊搜索，格式：{"field": "keyword"}
        time_range: 时间范围查询，格式：{"field": "create_time", "start": "2024-01-01", "end": "2024-12-31"}
        global_search: 全局多字段搜索，格式：{"keyword": "192.168", "fields": ["bk_host_innerip", "bk_host_name"]}
        page: 页码，从1开始
        size: 每页大小
        sort: 排序字段
        fields: 返回字段列表

    Returns:
        元组(总数, 实例列表)

    Example:
        >>> # OR查询：查询云区域为0或1的主机
        >>> total, instances = search_instances_advanced(
        ...     bk_obj_id="host",
        ...     or_query={"bk_cloud_id": [0, 1]}
        ... )

        >>> # 排除查询：排除已停止的主机
        >>> total, instances = search_instances_advanced(
        ...     bk_obj_id="host",
        ...     exclude_query={"bk_state": ["stopped", "terminated"]}
        ... )

        >>> # 时间范围查询：查询最近一个月创建的主机
        >>> total, instances = search_instances_advanced(
        ...     bk_obj_id="host",
        ...     time_range={
        ...         "field": "create_time",
        ...         "start": "2024-01-01 00:00:00",
        ...         "end": "2024-01-31 23:59:59"
        ...     }
        ... )

        >>> # 全局多字段搜索：在多个字段中搜索IP地址
        >>> total, instances = search_instances_advanced(
        ...     bk_obj_id="host",
        ...     global_search={
        ...         "keyword": "192.168",
        ...         "fields": ["bk_host_innerip", "bk_host_outerip"]
        ...     }
        ... )

        >>> # 组合复杂查询：业务ID + OR查询 + 排除 + 时间范围
        >>> total, instances = search_instances_advanced(
        ...     bk_obj_id="host",
        ...     bk_biz_id="2",
        ...     or_query={"bk_os_type": ["Linux", "Windows"]},
        ...     exclude_query={"bk_state": ["stopped"]},
        ...     time_range={
        ...         "field": "create_time",
        ...         "start": "2024-01-01",
        ...         "end": "2024-12-31"
        ...     }
        ... )
    """
    # 构建基础查询参数
    query_dict = _build_search_kwargs(
        bk_obj_id=bk_obj_id,
        bk_biz_id=bk_biz_id,
        bk_tenant_id=bk_tenant_id,
        cw_object_model_code=cw_object_model_code,
        cw_object_model_inst_id=cw_object_model_inst_id,
        query=query,
    )

    # 构建 get_query_instance 参数
    kwargs: dict[str, Any] = {"query": query_dict}

    if search:
        kwargs["search"] = search
    if or_query:
        kwargs["or_query"] = or_query
    if exclude_query:
        kwargs["exclude_query"] = exclude_query
    if exclude_search:
        kwargs["exclude_search"] = exclude_search
    if time_range:
        kwargs["time_field"] = time_range["field"]
        kwargs["start_time"] = time_range.get("start")
        kwargs["end_time"] = time_range.get("end")
    if global_search:
        kwargs["global_search"] = {
            "keyword": global_search["keyword"],
            "search_list": global_search["fields"],
        }
    if sort:
        kwargs["sort"] = sort
    if fields:
        kwargs["query_fields"] = fields

    # 使用 get_query_instance 构建查询
    s = CMDBInstance.get_query_instance(**kwargs)

    # 应用分页
    if page and size:
        start = (page - 1) * size
        s = s[start : start + size]
    elif size:
        s = s[:size]

    # 执行查询
    response = s.execute()
    total = response.hits.total.value if hasattr(response.hits.total, "value") else response.hits.total

    instances = [hit.to_dict() for hit in response.hits]
    return total, instances


def search_all_instances(
    bk_obj_id: str | None = None,
    bk_biz_id: str | None = None,
    bk_tenant_id: str | None = None,
    cw_object_model_code: str | None = None,
    cw_object_model_inst_id: str | None = None,
    query: dict[str, Any] | None = None,
    search: dict[str, str] | None = None,
    # 高级查询参数
    or_query: dict[str, Any] | None = None,
    exclude_query: dict[str, Any] | None = None,
    exclude_search: dict[str, str] | None = None,
    time_range: dict[str, Any] | None = None,
    global_search: dict[str, Any] | None = None,
    # 通用参数
    sort: str | None = None,
    fields: list[str] | None = None,
    batch_size: int = 1000,
    concurrent_count: int = 5,
    ignore_partial_error: bool = False,
) -> list[dict[str, Any]]:
    """搜索所有CMDB实例（自动分页，支持并发）。

    该函数会自动处理分页，获取所有符合条件的实例，适用于需要获取全量数据的场景。
    使用并发请求提高查询效率，适合数据量较大的场景。

    **查询模式自动选择**：
    - 如果使用了高级查询参数（or_query、exclude_query、time_range、global_search），
      则自动使用 search_instances_advanced
    - 否则使用 search_instances（性能更好）

    Args:
        bk_obj_id: CMDB模型ID
        bk_biz_id: 业务ID
        bk_tenant_id: 租户ID
        cw_object_model_code: 对象模型代码
        cw_object_model_inst_id: 对象模型实例ID
        query: 精确匹配参数
        search: 模糊匹配参数
        or_query: OR查询（高级查询）
        exclude_query: 排除查询（高级查询）
        exclude_search: 排除模糊搜索（高级查询）
        time_range: 时间范围查询（高级查询）
        global_search: 全局多字段搜索（高级查询）
        sort: 排序字段
        fields: 返回字段列表
        batch_size: 每批次大小，默认1000
        concurrent_count: 并发请求数，默认5
        ignore_partial_error: 是否忽略部分错误，默认False

    Returns:
        所有符合条件的实例列表

    Raises:
        Exception: 当某个分页请求失败且 ignore_partial_error=False 时抛出

    Example:
        >>> # 简单查询：获取某个业务下的所有主机实例
        >>> all_hosts = search_all_instances(bk_obj_id="host", bk_biz_id="2")
        >>> print(f"共有 {len(all_hosts)} 台主机")

        >>> # 高级查询：使用OR查询获取多个云区域的主机
        >>> all_hosts = search_all_instances(
        ...     bk_obj_id="host",
        ...     or_query={"bk_cloud_id": [0, 1, 2]}
        ... )

        >>> # 高级查询：排除已停止的主机
        >>> all_hosts = search_all_instances(
        ...     bk_obj_id="host",
        ...     exclude_query={"bk_state": ["stopped", "terminated"]}
        ... )

        >>> # 高级查询：时间范围查询
        >>> all_hosts = search_all_instances(
        ...     bk_obj_id="host",
        ...     time_range={
        ...         "field": "create_time",
        ...         "start": "2024-01-01",
        ...         "end": "2024-12-31"
        ...     }
        ... )

        >>> # 使用并发加速查询
        >>> all_hosts = search_all_instances(
        ...     bk_obj_id="host",
        ...     bk_biz_id="2",
        ...     batch_size=500,
        ...     concurrent_count=10
        ... )

        >>> # 只返回特定字段以节省内存
        >>> all_hosts = search_all_instances(
        ...     bk_obj_id="host",
        ...     bk_biz_id="2",
        ...     fields=["bk_inst_id", "bk_inst_name"]
        ... )
    """
    # 判断是否使用高级查询
    use_advanced = any([or_query, exclude_query, exclude_search, time_range, global_search])

    # 选择查询函数
    if use_advanced:
        search_func = search_instances_advanced
        search_kwargs = {
            "bk_obj_id": bk_obj_id,
            "bk_biz_id": bk_biz_id,
            "bk_tenant_id": bk_tenant_id,
            "cw_object_model_code": cw_object_model_code,
            "cw_object_model_inst_id": cw_object_model_inst_id,
            "query": query,
            "search": search,
            "or_query": or_query,
            "exclude_query": exclude_query,
            "exclude_search": exclude_search,
            "time_range": time_range,
            "global_search": global_search,
            "sort": sort,
            "fields": fields,
        }
    else:
        search_func = search_instances
        search_kwargs = {
            "bk_obj_id": bk_obj_id,
            "bk_biz_id": bk_biz_id,
            "bk_tenant_id": bk_tenant_id,
            "cw_object_model_code": cw_object_model_code,
            "cw_object_model_inst_id": cw_object_model_inst_id,
            "query": query,
            "search": search,
            "sort": sort,
            "fields": fields,
        }

    # 首次请求：获取第一页数据和总数
    first_total, first_instances = search_func(**search_kwargs, page=1, size=batch_size)  # pyright: ignore[reportArgumentType]

    # 如果总数为0或第一页已包含所有数据，直接返回
    if first_total == 0:
        return []

    if first_total <= batch_size:
        return first_instances

    # 计算总页数
    total_pages = math.ceil(first_total / batch_size)

    # 如果只有一页，直接返回第一页数据
    if total_pages <= 1:
        return first_instances

    # 构建剩余页码列表（排除第一页）
    remaining_pages = list(range(2, total_pages + 1))

    # 使用字典按页码顺序存储结果（包含第一页）
    page_results: dict[int, list[dict[str, Any]]] = {1: first_instances}

    # 使用线程池并发请求剩余页面
    with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
        # 提交所有剩余页面的请求任务
        future_to_page = {
            executor.submit(search_func, **search_kwargs, page=page, size=batch_size): page  # pyright: ignore[reportArgumentType]
            for page in remaining_pages
        }

        # 收集并发请求的结果
        for future in as_completed(future_to_page):
            page = future_to_page[future]
            try:
                _, page_instances = future.result()
                page_results[page] = page_instances
            except Exception as e:
                if not ignore_partial_error:
                    # 不忽略部分失败：直接抛出
                    logger.error(
                        f"search_all_instances: page {page} failed: {e}",
                        extra={"page": page, "batch_size": batch_size},
                    )
                    raise

                # 忽略部分失败：记录警告并继续
                logger.warning(
                    f"search_all_instances: page {page} failed: {e}",
                    extra={"page": page, "batch_size": batch_size},
                )

    # 按页码顺序合并所有结果
    all_instances: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        if page in page_results:
            all_instances.extend(page_results[page])

    return all_instances


def get_instance(
    bk_obj_id: str,
    bk_inst_id: int,
    cw_object_model_code: str | None = None,
    cw_object_model_inst_id: str | None = None,
) -> dict[str, Any] | None:
    """获取单个CMDB实例。

    Args:
        bk_obj_id: CMDB模型ID
        bk_inst_id: 实例ID
        cw_object_model_code: 对象模型代码，用于进一步过滤查询结果
        cw_object_model_inst_id: 对象模型实例ID，用于进一步过滤查询结果

    Returns:
        实例数据字典，如果实例不存在则返回None

    Example:
        >>> instance = get_instance("host", 12345)
        >>> if instance:
        ...     print(instance['bk_inst_name'])
        >>> else:
        ...     print("实例不存在")

        >>> # 使用对象模型代码查询
        >>> instance = get_instance(
        ...     "host", 12345,
        ...     cw_object_model_code="custom_model"
        ... )
    """
    doc_id = f"{bk_obj_id}_{bk_inst_id}"
    try:
        es_client = CMDBInstance.get_es_client()
        result = es_client.get(index=CMDBInstance.Index.ALIAS, id=doc_id)
        instance = result["_source"]

        # 如果指定了 cw_object_model_code 或 cw_object_model_inst_id，需要验证是否匹配
        if cw_object_model_code and instance.get("cw_object_model_code") != cw_object_model_code:
            return None
        if cw_object_model_inst_id and instance.get("cw_object_model_inst_id") != cw_object_model_inst_id:
            return None

        return instance
    except Exception as e:
        logger.warning(f"Get instance {doc_id} failed: {e}")
        return None


def query_option_values(
    fields: list[str],
    bk_obj_id: str | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, list[Any]]:
    """查询字段的可选值列表。

    用于获取某些字段的所有可能取值，常用于前端下拉框、筛选器等场景。
    支持查询任意CMDB字段的可选值。

    Args:
        fields: 需要查询可选值的字段列表
        bk_obj_id: CMDB模型ID，用于限定查询范围
        query: 额外的查询条件，用于在特定条件下获取可选值。
            支持任意CMDB字段作为过滤条件

    Returns:
        字段可选值字典，格式为{"field1": [value1, value2], "field2": [value3, value4]}

    Example:
        >>> # 查询主机的所有状态值和操作系统类型
        >>> options = query_option_values(
        ...     fields=["bk_state", "bk_os_type"],
        ...     bk_obj_id="host"
        ... )
        >>> print(options)
        {'bk_state': ['running', 'stopped'], 'bk_os_type': ['Linux', 'Windows']}

        >>> # 查询特定业务下主机的云区域ID选项
        >>> options = query_option_values(
        ...     fields=["bk_cloud_id"],
        ...     bk_obj_id="host",
        ...     query={"bk_biz_id": "2"}
        ... )

        >>> # 查询Linux主机的所有操作系统版本
        >>> options = query_option_values(
        ...     fields=["bk_os_version"],
        ...     bk_obj_id="host",
        ...     query={"bk_os_type": "Linux"}
        ... )
    """
    query_dict = query or {}
    if bk_obj_id:
        query_dict["bk_obj_id"] = bk_obj_id

    s = CMDBInstance.get_search(query=query_dict)
    return CMDBInstance.query_option_values(s, fields)


def search_obj_relations(
    bk_obj_id: str | None = None,
    bk_asst_obj_id: str | None = None,
    bk_obj_asst_id: str | None = None,
    query: dict[str, Any] | None = None,
    page: int | None = None,
    size: int | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """搜索CMDB模型关联关系。

    用于查询模型之间的关联定义，如主机和模块之间的"属于"关系定义。

    Args:
        bk_obj_id: CMDB模型ID（起点），如"host"
        bk_asst_obj_id: 关联目标模型ID（终点），如"module"
        bk_obj_asst_id: 模型关联关系ID，如"host_module"
        query: 精确匹配参数
        page: 页码
        size: 每页大小
        sort: 排序字段
        fields: 返回字段列表

    Returns:
        元组(总数, 关联关系列表)

    Example:
        >>> # 查询主机模型的所有关联关系
        >>> total, relations = search_obj_relations(bk_obj_id="host")
        >>> for rel in relations:
        ...     print(f"{rel['bk_obj_id']} -> {rel['bk_asst_obj_id']}")
    """
    query_dict = query or {}

    if bk_obj_id:
        query_dict["bk_obj_id"] = bk_obj_id
    if bk_asst_obj_id:
        query_dict["bk_asst_obj_id"] = bk_asst_obj_id
    if bk_obj_asst_id:
        query_dict["bk_obj_asst_id"] = bk_obj_asst_id

    s = CMDBObjRelate.get_search(
        query=query_dict,
        page=page,
        size=size,
        sort=sort,
        fields=fields,
    )

    response = s.execute()
    total = response.hits.total.value if hasattr(response.hits.total, "value") else response.hits.total

    relations = [hit.to_dict() for hit in response.hits]
    return total, relations


def search_inst_relations(
    bk_obj_id: str | None = None,
    bk_inst_id: str | None = None,
    bk_asst_obj_id: str | None = None,
    bk_asst_inst_id: str | None = None,
    bk_obj_asst_id: str | None = None,
    query: dict[str, Any] | None = None,
    page: int | None = None,
    size: int | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """搜索CMDB实例关联关系。

    用于查询实例之间的具体关联关系，如主机A属于模块B的关联关系。

    Args:
        bk_obj_id: CMDB模型ID（起点），如"host"
        bk_inst_id: 实例ID（起点），如"12345"
        bk_asst_obj_id: 关联目标模型ID（终点），如"module"
        bk_asst_inst_id: 关联目标实例ID（终点），如"67890"
        bk_obj_asst_id: 模型关联关系ID
        query: 精确匹配参数
        page: 页码
        size: 每页大小
        sort: 排序字段
        fields: 返回字段列表

    Returns:
        元组(总数, 实例关联关系列表)

    Example:
        >>> # 查询某个主机实例关联的所有模块
        >>> total, relations = search_inst_relations(
        ...     bk_obj_id="host",
        ...     bk_inst_id="12345",
        ...     bk_asst_obj_id="module"
        ... )
        >>> for rel in relations:
        ...     print(f"主机 {rel['bk_inst_id']} 属于模块 {rel['bk_asst_inst_id']}")
    """
    query_dict = query or {}

    if bk_obj_id:
        query_dict["bk_obj_id"] = bk_obj_id
    if bk_inst_id:
        query_dict["bk_inst_id"] = bk_inst_id
    if bk_asst_obj_id:
        query_dict["bk_asst_obj_id"] = bk_asst_obj_id
    if bk_asst_inst_id:
        query_dict["bk_asst_inst_id"] = bk_asst_inst_id
    if bk_obj_asst_id:
        query_dict["bk_obj_asst_id"] = bk_obj_asst_id

    s = CMDBInstRelate.get_search(
        query=query_dict,
        page=page,
        size=size,
        sort=sort,
        fields=fields,
    )

    response = s.execute()
    total = response.hits.total.value if hasattr(response.hits.total, "value") else response.hits.total

    relations = [hit.to_dict() for hit in response.hits]
    return total, relations


def search_all_inst_relations(
    bk_obj_id: str | None = None,
    bk_inst_id: str | None = None,
    query: dict[str, Any] | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
    batch_size: int = 1000,
    concurrent_count: int = 5,
    ignore_partial_error: bool = False,
) -> list[dict[str, Any]]:
    """搜索所有实例关联关系（自动分页，支持并发）。

    该函数会自动处理分页，获取所有符合条件的实例关联关系。
    使用并发请求提高查询效率，适合关联关系数量较大的场景。

    Args:
        bk_obj_id: CMDB模型ID
        bk_inst_id: 实例ID
        query: 精确匹配参数
        sort: 排序字段
        fields: 返回字段列表
        batch_size: 每批次大小，默认1000
        concurrent_count: 并发请求数，默认5
        ignore_partial_error: 是否忽略部分错误，默认False

    Returns:
        所有符合条件的实例关联关系列表

    Raises:
        Exception: 当某个分页请求失败且 ignore_partial_error=False 时抛出

    Example:
        >>> # 获取某个主机实例的所有关联关系
        >>> all_relations = search_all_inst_relations(
        ...     bk_obj_id="host",
        ...     bk_inst_id="12345"
        ... )
        >>> print(f"该主机有 {len(all_relations)} 个关联关系")

        >>> # 使用并发加速查询
        >>> all_relations = search_all_inst_relations(
        ...     bk_obj_id="host",
        ...     bk_inst_id="12345",
        ...     batch_size=500,
        ...     concurrent_count=10
        ... )

        >>> # 忽略部分错误继续查询
        >>> all_relations = search_all_inst_relations(
        ...     bk_obj_id="host",
        ...     bk_inst_id="12345",
        ...     ignore_partial_error=True
        ... )
    """
    # 首次请求：获取第一页数据和总数
    first_total, first_relations = search_inst_relations(
        bk_obj_id=bk_obj_id,
        bk_inst_id=bk_inst_id,
        query=query,
        page=1,
        size=batch_size,
        sort=sort,
        fields=fields,
    )

    # 如果总数为0或第一页已包含所有数据，直接返回
    if first_total == 0:
        return []

    if first_total <= batch_size:
        return first_relations

    # 计算总页数
    total_pages = math.ceil(first_total / batch_size)

    # 如果只有一页，直接返回第一页数据
    if total_pages <= 1:
        return first_relations

    # 构建剩余页码列表（排除第一页）
    remaining_pages = list(range(2, total_pages + 1))

    # 使用字典按页码顺序存储结果（包含第一页）
    page_results: dict[int, list[dict[str, Any]]] = {1: first_relations}

    # 使用线程池并发请求剩余页面
    with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
        # 提交所有剩余页面的请求任务
        future_to_page = {
            executor.submit(
                search_inst_relations,
                bk_obj_id=bk_obj_id,
                bk_inst_id=bk_inst_id,
                query=query,
                page=page,
                size=batch_size,
                sort=sort,
                fields=fields,
            ): page
            for page in remaining_pages
        }

        # 收集并发请求的结果
        for future in as_completed(future_to_page):
            page = future_to_page[future]
            try:
                _, page_relations = future.result()
                page_results[page] = page_relations
            except Exception as e:
                if not ignore_partial_error:
                    # 不忽略部分失败：直接抛出
                    logger.error(
                        f"search_all_inst_relations: page {page} failed: {e}",
                        extra={"page": page, "batch_size": batch_size},
                    )
                    raise

                # 忽略部分失败：记录警告并继续
                logger.warning(
                    f"search_all_inst_relations: page {page} failed: {e}",
                    extra={"page": page, "batch_size": batch_size},
                )

    # 按页码顺序合并所有结果
    all_relations: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        if page in page_results:
            all_relations.extend(page_results[page])

    return all_relations


def get_instance_with_relations(
    bk_obj_id: str,
    bk_inst_id: int,
    include_relations: bool = True,
) -> dict[str, Any] | None:
    """获取实例及其关联关系。

    获取实例的完整信息，包括实例本身的属性数据，以及该实例作为起点和终点的所有关联关系。

    Args:
        bk_obj_id: CMDB模型ID
        bk_inst_id: 实例ID
        include_relations: 是否包含关联关系，默认为True

    Returns:
        实例数据字典（包含关联关系），如果实例不存在则返回None。
        返回的字典包含以下额外字段：
        - source_relations: 该实例作为起点的关联关系列表
        - target_relations: 该实例作为终点的关联关系列表

    Example:
        >>> # 获取主机实例及其所有关联关系
        >>> instance = get_instance_with_relations("host", 12345)
        >>> if instance:
        ...     print(f"实例名称: {instance['bk_inst_name']}")
        ...     print(f"作为起点的关联: {len(instance['source_relations'])} 个")
        ...     print(f"作为终点的关联: {len(instance['target_relations'])} 个")

        >>> # 只获取实例本身，不包含关联关系
        >>> instance = get_instance_with_relations(
        ...     "host", 12345, include_relations=False
        ... )
    """
    instance = get_instance(bk_obj_id, bk_inst_id)
    if not instance:
        return None

    if include_relations:
        # 查询该实例作为起点的关联关系
        _, source_relations = search_inst_relations(
            bk_obj_id=bk_obj_id,
            bk_inst_id=str(bk_inst_id),
            size=10000,
        )
        # 查询该实例作为终点的关联关系
        _, target_relations = search_inst_relations(
            bk_asst_obj_id=bk_obj_id,
            bk_asst_inst_id=str(bk_inst_id),
            size=10000,
        )

        instance["source_relations"] = source_relations
        instance["target_relations"] = target_relations

    return instance


def search_instances_by_dsl(
    dsl: dict[str, Any],
    page: int | None = None,
    size: int | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """使用Elasticsearch DSL查询CMDB实例。

    在极端复杂的查询场景下，可以直接使用Elasticsearch DSL进行查询，
    提供最大的灵活性和查询能力。

    Args:
        dsl: Elasticsearch查询DSL字典，符合ES Query DSL语法
        page: 页码，从1开始
        size: 每页大小
        sort: 排序字段，如"-create_time"表示按create_time降序
        fields: 返回字段列表

    Returns:
        元组(总数, 实例列表)，其中总数为符合条件的实例总数，实例列表为当前页的实例数据

    Example:
        >>> # 使用bool查询组合多个条件
        >>> dsl = {
        ...     "bool": {
        ...         "must": [
        ...             {"term": {"bk_obj_id": "host"}},
        ...             {"term": {"bk_biz_id": "2"}}
        ...         ],
        ...         "filter": [
        ...             {"range": {"bk_mem": {"gte": 8192}}}
        ...         ],
        ...         "should": [
        ...             {"term": {"bk_os_type": "Linux"}},
        ...             {"term": {"bk_os_type": "Windows"}}
        ...         ],
        ...         "minimum_should_match": 1
        ...     }
        ... }
        >>> total, instances = search_instances_by_dsl(dsl, page=1, size=10)

        >>> # 使用terms查询多个值
        >>> dsl = {
        ...     "bool": {
        ...         "must": [
        ...             {"terms": {"bk_host_innerip": ["192.168.1.1", "192.168.1.2"]}}
        ...         ]
        ...     }
        ... }
        >>> total, instances = search_instances_by_dsl(dsl)

        >>> # 使用wildcard进行通配符查询
        >>> dsl = {
        ...     "wildcard": {
        ...         "bk_host_name": "*prod*"
        ...     }
        ... }
        >>> total, instances = search_instances_by_dsl(dsl)

        >>> # 使用nested查询嵌套对象
        >>> dsl = {
        ...     "nested": {
        ...         "path": "process",
        ...         "query": {
        ...             "bool": {
        ...                 "must": [
        ...                     {"match": {"process.name": "nginx"}}
        ...                 ]
        ...             }
        ...         }
        ...     }
        ... }
        >>> total, instances = search_instances_by_dsl(dsl)

        >>> # 使用aggregation进行聚合查询
        >>> dsl = {
        ...     "match_all": {}
        ... }
        >>> total, instances = search_instances_by_dsl(
        ...     dsl,
        ...     fields=["bk_obj_id", "bk_biz_id"]
        ... )
    """

    # 创建基础搜索对象
    s = CMDBInstance.search()

    # 应用DSL查询
    if dsl:
        s = s.update_from_dict({"query": dsl})

    # 应用分页
    if page and size:
        start = (page - 1) * size
        s = s[start : start + size]
    elif size:
        s = s[:size]

    # 应用排序
    if sort:
        s = s.sort(sort)

    # 应用字段过滤
    if fields:
        s = s.source(fields)

    # 执行查询
    response: Response = cast(Response, s.execute())
    total_value: int | Any = response.hits.total.value if hasattr(response.hits.total, "value") else response.hits.total
    total = int(total_value) if total_value is not None else 0

    instances: list[dict[str, Any]] = [hit.to_dict() for hit in response.hits]  # pyright: ignore[reportAssignmentType]
    return total, instances


def search_all_instances_by_dsl(
    dsl: dict[str, Any],
    sort: str | None = None,
    fields: list[str] | None = None,
    batch_size: int = 1000,
    concurrent_count: int = 5,
    ignore_partial_error: bool = False,
) -> list[dict[str, Any]]:
    """使用Elasticsearch DSL查询所有CMDB实例（自动分页，支持并发）。

    该函数会自动处理分页，获取所有符合DSL查询条件的实例。
    使用并发请求提高查询效率。注意：如果数据量很大，可能会耗费较长时间和内存。

    Args:
        dsl: Elasticsearch查询DSL字典
        sort: 排序字段
        fields: 返回字段列表
        batch_size: 每批次大小，默认1000
        concurrent_count: 并发请求数，默认5
        ignore_partial_error: 是否忽略部分错误，默认False

    Returns:
        所有符合条件的实例列表

    Raises:
        Exception: 当某个分页请求失败且 ignore_partial_error=False 时抛出

    Example:
        >>> # 使用复杂DSL查询所有符合条件的主机
        >>> dsl = {
        ...     "bool": {
        ...         "must": [
        ...             {"term": {"bk_obj_id": "host"}},
        ...             {"range": {"bk_cpu": {"gte": 4}}}
        ...         ]
        ...     }
        ... }
        >>> all_instances = search_all_instances_by_dsl(dsl)
        >>> print(f"共找到 {len(all_instances)} 个实例")

        >>> # 使用并发加速查询
        >>> all_instances = search_all_instances_by_dsl(
        ...     dsl,
        ...     batch_size=500,
        ...     concurrent_count=10
        ... )

        >>> # 只返回特定字段以节省内存
        >>> all_instances = search_all_instances_by_dsl(
        ...     dsl,
        ...     fields=["bk_inst_id", "bk_host_innerip"]
        ... )
    """
    # 首次请求：获取第一页数据和总数
    first_total, first_instances = search_instances_by_dsl(
        dsl=dsl,
        page=1,
        size=batch_size,
        sort=sort,
        fields=fields,
    )

    # 如果总数为0或第一页已包含所有数据，直接返回
    if first_total == 0:
        return []

    if first_total <= batch_size:
        return first_instances

    # 计算总页数
    total_pages = math.ceil(first_total / batch_size)

    # 如果只有一页，直接返回第一页数据
    if total_pages <= 1:
        return first_instances

    # 构建剩余页码列表（排除第一页）
    remaining_pages = list(range(2, total_pages + 1))

    # 使用字典按页码顺序存储结果（包含第一页）
    page_results: dict[int, list[dict[str, Any]]] = {1: first_instances}

    # 使用线程池并发请求剩余页面
    with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
        # 提交所有剩余页面的请求任务
        future_to_page = {
            executor.submit(
                search_instances_by_dsl,
                dsl=dsl,
                page=page,
                size=batch_size,
                sort=sort,
                fields=fields,
            ): page
            for page in remaining_pages
        }

        # 收集并发请求的结果
        for future in as_completed(future_to_page):
            page = future_to_page[future]
            try:
                _, page_instances = future.result()
                page_results[page] = page_instances
            except Exception as e:
                if not ignore_partial_error:
                    # 不忽略部分失败：直接抛出
                    logger.error(
                        f"search_all_instances_by_dsl: page {page} failed: {e}",
                        extra={"page": page, "batch_size": batch_size},
                    )
                    raise

                # 忽略部分失败：记录警告并继续
                logger.warning(
                    f"search_all_instances_by_dsl: page {page} failed: {e}",
                    extra={"page": page, "batch_size": batch_size},
                )

    # 按页码顺序合并所有结果
    all_instances: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        if page in page_results:
            all_instances.extend(page_results[page])

    return all_instances


def iter_instances(
    bk_obj_id: str | None = None,
    bk_inst_ids: list[int] | None = None,
    bk_biz_id: str | None = None,
    bk_biz_ids: list[str] | None = None,
    bk_tenant_id: str | None = None,
    dynamic_group_id: str | None = None,
    cw_object_model_code: str | None = None,
    cw_object_model_inst_id: str | None = None,
    query: dict[str, Any] | None = None,
    search: dict[str, str] | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
    batch_size: int = 1000,
) -> Iterator[list[dict[str, Any]]]:
    """迭代查询CMDB实例（流式处理，节省内存）。

    返回一个迭代器，逐批次加载数据，每次 yield 一批实例列表，适用于处理大量数据的场景。
    相比 search_all_instances，此函数不会一次性加载所有数据到内存，
    而是按批次逐步查询和返回，由使用者控制数据的处理和释放。

    Args:
        bk_obj_id: CMDB模型ID，如"host"、"module"等
        bk_inst_ids: 实例ID列表，用于批量查询特定实例
        bk_biz_id: 业务ID，用于过滤特定业务下的实例
        bk_biz_ids: 业务ID列表，用于查询多个业务的实例
        bk_tenant_id: 租户ID，用于过滤特定租户下的实例
        dynamic_group_id: 动态分组ID，用于查询动态分组中的实例
        cw_object_model_code: 对象模型代码，用于查询特定对象模型的实例
        cw_object_model_inst_id: 对象模型实例ID，用于查询特定对象模型实例
        query: 精确匹配参数，支持查询任意CMDB字段
        search: 模糊匹配参数，支持对任意字段进行模糊搜索
        sort: 排序字段，如"-create_time"表示降序
        fields: 返回字段列表，用于指定需要返回的字段
        batch_size: 每批次大小，默认1000

    Yields:
        每次返回一批实例列表（list[dict]）

    Example:
        >>> # 迭代处理所有主机实例（按批次）
        >>> for batch_instances in iter_instances(bk_obj_id="host", bk_tenant_id="tenant1"):
        ...     print(f"处理一批 {len(batch_instances)} 个主机")
        ...     for instance in batch_instances:
        ...         print(f"  - 主机: {instance['bk_host_name']}")
        ...     # 处理完这批后立即释放，不占用内存

        >>> # 统计所有Linux主机的数量
        >>> count = 0
        >>> for batch_instances in iter_instances(
        ...     bk_obj_id="host",
        ...     query={"bk_os_type": "Linux"}
        ... ):
        ...     count += len(batch_instances)
        >>> print(f"Linux主机数量: {count}")

        >>> # 批量写入数据库（每批直接写入）
        >>> for batch_instances in iter_instances(bk_obj_id="host", bk_biz_id="2"):
        ...     # 每批数据直接写入数据库
        ...     save_to_database(batch_instances)
        ...     print(f"已保存 {len(batch_instances)} 条记录")

        >>> # 查找后立即停止
        >>> for batch_instances in iter_instances(bk_obj_id="host"):
        ...     for instance in batch_instances:
        ...         if instance['bk_host_innerip'] == "192.168.1.1":
        ...             print("找到目标主机")
        ...             break
        ...     else:
        ...         continue  # 未找到，继续下一批
        ...     break  # 找到后停止迭代

        >>> # 使用更简洁的方式统计
        >>> total = sum(len(batch) for batch in iter_instances(bk_obj_id="host"))
        >>> print(f"总共 {total} 台主机")
    """
    return _paginate(
        search_instances,
        batch_size=batch_size,
        bk_obj_id=bk_obj_id,
        bk_inst_ids=bk_inst_ids,
        bk_biz_id=bk_biz_id,
        bk_biz_ids=bk_biz_ids,
        bk_tenant_id=bk_tenant_id,
        dynamic_group_id=dynamic_group_id,
        cw_object_model_code=cw_object_model_code,
        cw_object_model_inst_id=cw_object_model_inst_id,
        query=query,
        search=search,
        sort=sort,
        fields=fields,
    )


def iter_inst_relations(
    bk_obj_id: str | None = None,
    bk_inst_id: str | None = None,
    bk_asst_obj_id: str | None = None,
    bk_asst_inst_id: str | None = None,
    bk_obj_asst_id: str | None = None,
    query: dict[str, Any] | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
    batch_size: int = 1000,
) -> Iterator[list[dict[str, Any]]]:
    """迭代查询实例关联关系（流式处理，节省内存）。

    返回一个迭代器，逐批次加载关联关系数据，每次 yield 一批关联关系列表，
    适用于处理大量关联关系的场景。

    Args:
        bk_obj_id: CMDB模型ID（起点），如"host"
        bk_inst_id: 实例ID（起点），如"12345"
        bk_asst_obj_id: 关联目标模型ID（终点），如"module"
        bk_asst_inst_id: 关联目标实例ID（终点），如"67890"
        bk_obj_asst_id: 模型关联关系ID
        query: 精确匹配参数
        sort: 排序字段
        fields: 返回字段列表
        batch_size: 每批次大小，默认1000

    Yields:
        每次返回一批关联关系列表（list[dict]）

    Example:
        >>> # 迭代处理某个主机的所有关联关系（按批次）
        >>> for batch_relations in iter_inst_relations(
        ...     bk_obj_id="host",
        ...     bk_inst_id="12345"
        ... ):
        ...     print(f"处理一批 {len(batch_relations)} 个关联关系")
        ...     for relation in batch_relations:
        ...         print(f"  - 关联到: {relation['bk_asst_obj_id']}:{relation['bk_asst_inst_id']}")

        >>> # 统计关联关系数量
        >>> count = sum(len(batch) for batch in iter_inst_relations(bk_obj_id="host"))
        >>> print(f"主机关联关系总数: {count}")

        >>> # 批量处理关联关系
        >>> for batch_relations in iter_inst_relations(bk_obj_id="host", bk_inst_id="12345"):
        ...     process_relations_batch(batch_relations)
    """
    return _paginate(
        search_inst_relations,
        batch_size=batch_size,
        bk_obj_id=bk_obj_id,
        bk_inst_id=bk_inst_id,
        bk_asst_obj_id=bk_asst_obj_id,
        bk_asst_inst_id=bk_asst_inst_id,
        bk_obj_asst_id=bk_obj_asst_id,
        query=query,
        sort=sort,
        fields=fields,
    )


def iter_instances_by_dsl(
    dsl: dict[str, Any],
    sort: str | None = None,
    fields: list[str] | None = None,
    batch_size: int = 1000,
) -> Iterator[list[dict[str, Any]]]:
    """使用Elasticsearch DSL迭代查询CMDB实例（流式处理，节省内存）。

    返回一个迭代器，逐批次加载数据，每次 yield 一批实例列表，
    适用于使用复杂DSL查询大量数据的场景。

    Args:
        dsl: Elasticsearch查询DSL字典，符合ES Query DSL语法
        sort: 排序字段，如"-create_time"表示降序
        fields: 返回字段列表
        batch_size: 每批次大小，默认1000

    Yields:
        每次返回一批实例列表（list[dict]）

    Example:
        >>> # 使用复杂DSL迭代查询（按批次）
        >>> dsl = {
        ...     "bool": {
        ...         "must": [
        ...             {"term": {"bk_obj_id": "host"}},
        ...             {"range": {"bk_mem": {"gte": 8192}}}
        ...         ]
        ...     }
        ... }
        >>> for batch_instances in iter_instances_by_dsl(dsl):
        ...     print(f"处理一批 {len(batch_instances)} 个高配置主机")
        ...     for instance in batch_instances:
        ...         print(f"  - {instance['bk_host_name']}")

        >>> # 使用迭代器配合批量处理
        >>> dsl = {"term": {"bk_obj_id": "host"}}
        >>> for batch_instances in iter_instances_by_dsl(dsl, batch_size=500):
        ...     # 过滤Linux主机
        ...     linux_hosts = [inst for inst in batch_instances if inst.get('bk_os_type') == 'Linux']
        ...     if linux_hosts:
        ...         process_linux_hosts(linux_hosts)

        >>> # 统计总数
        >>> total = sum(len(batch) for batch in iter_instances_by_dsl(dsl))
        >>> print(f"总共 {total} 个实例")
    """
    return _paginate(
        search_instances_by_dsl,
        batch_size=batch_size,
        dsl=dsl,
        sort=sort,
        fields=fields,
    )
