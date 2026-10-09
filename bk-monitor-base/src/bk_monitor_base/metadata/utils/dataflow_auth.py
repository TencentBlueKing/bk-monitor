import json
import logging

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.metadata.config import settings

logger = logging.getLogger("bkmonitor.dataflow")


def check_has_permission(project_id: int, rt_id: str):
    # 1. 效验表是否有权限
    try:
        has_permission = api.bkdata.auth_projects_data_check(
            bk_tenant_id=DEFAULT_TENANT_ID, project_id=project_id, result_table_id=rt_id
        )
    except BkApiError:
        logger.exception(f"check whether the project({project_id}) has the permission of ({rt_id}) table, error.")
        return False

    return has_permission


def ensure_has_permission_with_rt_id(bk_username: str, rt_id: str, project_id: int | None = None):
    project_id: int = project_id or settings.metadata.bk_data_project_id
    if not check_has_permission(project_id, rt_id):
        try:
            # 针对结果表直接授权给项目
            result = api.bkdata.auth_result_table(
                bk_tenant_id=DEFAULT_TENANT_ID,
                project_id=project_id,
                object_id=rt_id,
                bk_biz_id=int(rt_id.split("_")[0]),
            )
        except Exception:  # noqa
            logger.exception(f"failed to grant permission({rt_id})")
            return False
        logger.info("grant permission successfully(%s), result:%s", rt_id, result)

    return True


def batch_add_permission(project_id: int, bk_biz_id: int, table_id_list: list[str]) -> bool:
    """批量检查项目是否有结果表的权限"""
    project_id = project_id or settings.metadata.bk_data_project_id
    # 如果检测异常，则全量再授权一次
    try:
        table_id_perm = api.bkdata.query_auth_projects_data(
            bk_tenant_id=DEFAULT_TENANT_ID, project_id=project_id, object_ids=table_id_list
        )
        need_auth_table_id_list: list[str] = table_id_perm.get("no_permissions") or []
    except BkApiError as e:
        logger.error(
            "check whether the project: %s has the permission of %s table, error: %s",
            project_id,
            json.dumps(table_id_list),
            e,
        )
        need_auth_table_id_list: list[str] = table_id_list
    if not need_auth_table_id_list:
        return True
    # 授权结果表
    try:
        api.bkdata.batch_auth_result_table(
            bk_tenant_id=DEFAULT_TENANT_ID,
            project_id=project_id,
            object_ids=need_auth_table_id_list,
            bk_biz_id=bk_biz_id,
        )
    except BkApiError as e:
        logger.error(
            "add project: %s prem to access table: %s error: %s", project_id, json.dumps(need_auth_table_id_list), e
        )
        return False

    return True
