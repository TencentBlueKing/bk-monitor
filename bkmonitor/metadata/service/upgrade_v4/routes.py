"""升级路由散件：空集合不触发全量刷新，space 只在显式选择时刷新。"""

from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

ROUTE_MODES = {"none", "rt", "data_label", "rt_and_data_label", "all"}


class UpgradeRouter(SpaceTableIDRedis):
    def _compose_record_rule_table_id_detail(self, bk_tenant_id):
        # 仅刷新指定 RT，不附带整个租户的预计算规则。
        return {}


def refresh_routes(*, table_ids=(), spaces=(), mode="rt_and_data_label", is_publish=True, bk_tenant_id="system"):
    """all 表示 RT/label 及传入的空间，不表示全租户；spaces 为 (type, id) 序列。"""
    if mode not in ROUTE_MODES:
        raise ValueError(f"未知路由刷新模式: {mode}")
    table_ids = list(dict.fromkeys(table_ids))
    spaces = list(dict.fromkeys(tuple(space) for space in spaces))
    router = UpgradeRouter()
    if table_ids and mode in {"rt", "rt_and_data_label", "all"}:
        router.push_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=table_ids, is_publish=is_publish)
    if table_ids and mode in {"data_label", "rt_and_data_label", "all"}:
        router.push_data_label_table_ids(bk_tenant_id=bk_tenant_id, table_id_list=table_ids, is_publish=is_publish)
    if mode == "all":
        for space_type, space_id in spaces:
            router.push_space_table_ids(space_type, space_id, is_publish=is_publish)
    return {"mode": mode, "table_ids": table_ids, "spaces": spaces if mode == "all" else []}
