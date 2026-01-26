import copy

from bkm_ipchooser.constants import CommonEnum
from bkm_ipchooser.tools.batch_request import QUERY_CMDB_LIMIT, batch_request, QUERY_CMDB_MODULE_LIMIT


def get_pagination_data(func, params: dict, split_params=False) -> dict:
    """
    前端透传分页参数, 获取分页数据/全量数据
    适配page_size为-1获取CC全量数据的情况
    return: {}
    """
    sort_field = params.get("page", {}).get("sort", "bk_host_innerip")

    # 判断是否全部获取
    if params.get("page", {}).get("limit", QUERY_CMDB_LIMIT) == CommonEnum.PAGE_RETURN_ALL_FLAG.value:
        # 多线程补充no_request参数
        params["no_request"] = True
        sort = sort_field
        params.pop("page", None)
        info = batch_request(func=func, params=params, sort=sort, split_params=split_params)
        result = {"count": len(info), "info": info}
    else:
        result = pagination_query(func, params, split_params)

    if split_params and result.get("info"):
        sorted_info = sorted(result.get("info"), key=lambda x: x.get(sort_field, ""), reverse=False)
        result["info"] = sorted_info

    return result


def pagination_query(func, params: dict, split_params=False):
    """
    分页查询
    """
    # 获取分页参数中的 start、limit
    start, limit = get_page_start_and_limit(params)

    if not split_params:
        # 当 bk_module_ids 数量不超过 500 个限制时, 直接查询
        return direct_query(func, params, start, limit)
    else:
        # 当 bk_module_ids 数量超过 500 个限制时, 分批查询
        return split_query(func, params, start, limit)


def get_page_start_and_limit(params: dict):
    """
    获取分页参数中的 start、limit
    """
    params_page = params.get("page", {})
    start = params_page.get("start", 0)
    limit = params_page.get("limit", QUERY_CMDB_LIMIT)
    return start, limit


def direct_query(func, params: dict, start, limit):
    """
    直接查询, 限制每次查询最大数量为 500 条
    """
    info = []
    total_count = 0
    got_total_count = False

    query_params = copy.deepcopy(params)

    while limit > 0:
        query_params["page"]["start"] = start
        query_params["page"]["limit"] = min(limit, QUERY_CMDB_LIMIT)

        response = func(query_params)
        batch_info = response.get("info", [])
        if not got_total_count:
            total_count = response.get("count", 0)
            got_total_count = True

        if not batch_info:
            break

        info.extend(batch_info)
        start += len(batch_info)
        limit -= len(batch_info)

    return {"count": total_count, "info": info}


def split_query(func, params: dict, start, limit):
    """
    拆分 bk_module_ids 分批查询, 限制每次查询最大数量为 500 条
    """
    bk_module_ids = params.get("bk_module_ids", [])

    info = []
    total_count = 0
    accumulated = 0

    query_batch_total_count_params = {**params, "page": {"start": 0, "limit": 1}}

    # 分批查询, 按照每批 500 个 bk_module_ids 进行拆分
    for index in range(0, len(bk_module_ids), QUERY_CMDB_MODULE_LIMIT):
        batch_bk_module_ids = bk_module_ids[index : index + QUERY_CMDB_MODULE_LIMIT]

        query_batch_total_count_params["bk_module_ids"] = batch_bk_module_ids

        # 查询本批次所拥有的 host 总数
        batch_total_count = func(query_batch_total_count_params).get("count", 0)

        total_count += batch_total_count

        if not batch_total_count or limit <= 0:
            continue

        if start < total_count:
            query_params = copy.deepcopy(params)
            query_params["bk_module_ids"] = batch_bk_module_ids

            batch_start = max(0, start - accumulated)
            while limit > 0 and batch_start < batch_total_count:
                batch_limit = min(batch_total_count - batch_start, limit, QUERY_CMDB_LIMIT)

                query_params["page"]["start"] = batch_start
                query_params["page"]["limit"] = batch_limit

                response = func(query_params)
                batch_info = response.get("info", [])

                if not batch_info:
                    break

                info.extend(batch_info)
                batch_start += len(batch_info)
                limit -= len(batch_info)

        accumulated += batch_total_count

    return {"count": total_count, "info": info}
