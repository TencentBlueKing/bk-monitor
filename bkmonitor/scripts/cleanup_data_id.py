"""
粘贴到 ipython shell 中即可执行。

这个脚本只定义函数，不会自动执行清理。

核心能力：
1. cleanup_data_id(data_id): 清理单个 data_id
2. cleanup_data_ids(data_ids): 批量清理多个 data_id，单个失败不影响后续

清理步骤：
1. 查询并禁用 datasource
2. 查询并禁用关联 result table
3. 清理 GSE route 配置

设计原则：
1. 可重入：重复执行不会因为对象已经是 disable / route 已不存在而失败
2. 单个 data_id 出错不影响其他 data_id
3. 返回结构化结果，方便后续审计和二次处理
"""

from typing import Any

from django.conf import settings

from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config, models


DEFAULT_OPERATOR = getattr(settings, "COMMON_USERNAME", "system")


def _result(status: str, detail: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]:
    """统一步骤返回结构，方便批量执行时直接汇总。"""
    return {
        "status": status,
        "detail": detail or {},
        "error": error,
    }


def _disable_datasource(datasource: models.DataSource, operator: str) -> dict[str, Any]:
    """禁用 datasource，并确保 consul 配置被删除。

    可重入保证：
    - datasource 已经是 disable 时，不报错
    - consul 路径即使不存在，delete_consul_config 也允许重复执行
    """
    before_enabled = datasource.is_enable

    if datasource.is_enable:
        datasource.is_enable = False
        datasource.last_modify_user = operator
        datasource.save()

    datasource.delete_consul_config()

    return _result(
        status="success",
        detail={
            "bk_data_id": datasource.bk_data_id,
            "created_from": datasource.created_from,
            "was_enabled": before_enabled,
            "is_enable": datasource.is_enable,
            "consul_deleted": True,
        },
    )


def _disable_result_tables(data_id: int, operator: str) -> dict[str, Any]:
    """禁用 data_id 关联的所有 ResultTable。

    可重入保证：
    - ResultTable 已经 disable 时，直接标记 skipped，不重复做破坏性操作
    - 不直接改 is_deleted，只按需求做 disable
    """
    dsrt_list = list(models.DataSourceResultTable.objects.filter(bk_data_id=data_id).values("table_id", "bk_tenant_id"))

    result = {
        "total": len(dsrt_list),
        "success": [],
        "skipped": [],
        "failed": [],
    }

    for dsrt in dsrt_list:
        table_id = dsrt["table_id"]
        bk_tenant_id = dsrt["bk_tenant_id"]

        try:
            result_table = models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        except models.ResultTable.DoesNotExist:
            result["failed"].append(
                {
                    "table_id": table_id,
                    "bk_tenant_id": bk_tenant_id,
                    "error": "result table not found",
                }
            )
            continue

        if not result_table.is_enable:
            result["skipped"].append(
                {
                    "table_id": result_table.table_id,
                    "bk_tenant_id": result_table.bk_tenant_id,
                    "reason": "already disabled",
                }
            )
            continue

        try:
            result_table.modify(operator=operator, is_enable=False)
            result["success"].append(
                {
                    "table_id": result_table.table_id,
                    "bk_tenant_id": result_table.bk_tenant_id,
                }
            )
        except Exception as error:  # pylint: disable=broad-except
            result["failed"].append(
                {
                    "table_id": result_table.table_id,
                    "bk_tenant_id": result_table.bk_tenant_id,
                    "error": str(error),
                }
            )

    status = "success" if not result["failed"] else "partial_success"
    return _result(status=status, detail=result)


def _cleanup_gse_route(data_id: int, operator: str) -> dict[str, Any]:
    """删除 data_id 的 GSE route。

    可重入保证：
    - route 不存在时返回 skipped
    - route 已被删除时，重复执行不会报错
    """
    query_params = {
        "condition": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": data_id},
        "operation": {"operator_name": operator},
    }

    try:
        routes = api.gse.query_route(**query_params)
    except BKAPIError as error:
        return _result(status="failed", error=f"query gse route failed: {error}")

    if not routes:
        return _result(status="skipped", detail={"bk_data_id": data_id, "reason": "gse route not found"})

    delete_params = {
        "condition": {"channel_id": data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
        "operation": {"operator_name": operator, "method": "all"},
    }
    try:
        api.gse.delete_route(delete_params)
        return _result(status="success", detail={"bk_data_id": data_id, "deleted": True})
    except BKAPIError as error:
        return _result(status="failed", error=f"delete gse route failed: {error}")


def cleanup_data_id(data_id: int, operator: str = DEFAULT_OPERATOR) -> dict[str, Any]:
    """清理单个 data_id。

    返回结构示例：
    {
        "data_id": 123,
        "success": True,
        "has_error": False,
        "errors": [],
        "steps": {
            "datasource": {...},
            "result_tables": {...},
            "gse_route": {...},
        }
    }
    """
    result = {
        "data_id": data_id,
        "success": False,
        "has_error": False,
        "errors": [],
        "steps": {},
    }

    try:
        datasource = models.DataSource.objects.get(bk_data_id=data_id)
    except models.DataSource.DoesNotExist:
        result["has_error"] = True
        result["errors"].append(f"data_id {data_id} not found")
        result["steps"]["datasource"] = _result(status="failed", error="datasource not found")
        return result

    # 步骤一：禁用 datasource
    try:
        result["steps"]["datasource"] = _disable_datasource(datasource, operator)
    except Exception as error:  # pylint: disable=broad-except
        result["has_error"] = True
        result["errors"].append(f"disable datasource failed: {error}")
        result["steps"]["datasource"] = _result(status="failed", error=str(error))

    # 步骤二：禁用关联 result table
    try:
        rt_result = _disable_result_tables(data_id, operator)
        result["steps"]["result_tables"] = rt_result
        if rt_result["status"] == "partial_success":
            result["has_error"] = True
            result["errors"].append("disable result tables partial failed")
    except Exception as error:  # pylint: disable=broad-except
        result["has_error"] = True
        result["errors"].append(f"disable result tables failed: {error}")
        result["steps"]["result_tables"] = _result(status="failed", error=str(error))

    # 步骤三：清理 GSE route
    try:
        gse_result = _cleanup_gse_route(data_id, operator)
        result["steps"]["gse_route"] = gse_result
        if gse_result["status"] == "failed":
            result["has_error"] = True
            result["errors"].append(gse_result["error"])
    except Exception as error:  # pylint: disable=broad-except
        result["has_error"] = True
        result["errors"].append(f"cleanup gse route failed: {error}")
        result["steps"]["gse_route"] = _result(status="failed", error=str(error))

    result["success"] = not result["has_error"]
    return result


def cleanup_data_ids(data_ids: list[int], operator: str = DEFAULT_OPERATOR) -> list[dict[str, Any]]:
    """批量清理多个 data_id。

    这里显式逐个调用 cleanup_data_id，确保单个 data_id 报错不会打断后续循环。
    """
    results = []
    for data_id in data_ids:
        try:
            results.append(cleanup_data_id(data_id=data_id, operator=operator))
        except Exception as error:  # pylint: disable=broad-except
            results.append(
                {
                    "data_id": data_id,
                    "success": False,
                    "has_error": True,
                    "errors": [f"unexpected error: {error}"],
                    "steps": {},
                }
            )
    return results


# 使用示例：
# result = cleanup_data_id(1500001)
# results = cleanup_data_ids([1500001, 1500002, 1500003])
