from bk_dataview.models import Dashboard, DataSource, Org, Preferences, Star
from monitor_web.data_migrate.fetcher.base import FetcherResultType


def _resolve_org_ids(bk_biz_id: int | None) -> list[int] | None:
    """将 bk_biz_id 映射为 Grafana Org ID 列表。

    Grafana 中 Org.name 存储的是 str(bk_biz_id)，通过反查获取对应的 org.id。
    bk_biz_id 为 None 时返回 None，表示不做过滤（全量导出）。
    """
    if bk_biz_id is None:
        return None
    return list(Org.objects.filter(name=str(bk_biz_id)).values_list("id", flat=True))


def get_bk_dataview_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """获取 bk_dataview 仪表盘相关模型的迁移 ORM 查询配置。

    迁移范围包括：
    - Org: 组织记录（bk_biz_id 与 Grafana org 的映射）
    - DataSource: 数据源配置
    - Dashboard: 仪表盘定义
    - Star: 用户收藏
    - Preferences: 用户偏好设置

    所有表通过 org_id 关联，Star 通过 dashboard_id 间接关联。
    """
    org_ids = _resolve_org_ids(bk_biz_id)
    org_filters = None if org_ids is None else {"id__in": org_ids}
    org_id_filters = None if org_ids is None else {"org_id__in": org_ids}

    dashboard_ids = Dashboard.objects.filter(**(org_id_filters or {})).values_list("id", flat=True)
    star_filters: dict | None = None
    if org_ids is not None:
        star_filters = {"dashboard_id__in": dashboard_ids}

    return [
        (Org, org_filters, None),
        (DataSource, org_id_filters, None),
        (Dashboard, org_id_filters, None),
        (Star, star_filters, None),
        (Preferences, org_id_filters, None),
    ]
