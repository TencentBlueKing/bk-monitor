from bkmonitor.models.query_template import QueryTemplate
from monitor_web.data_migrate.fetcher.base import FetcherResultType
from monitor_web.models.data_explorer import FavoriteGroup, QueryHistory
from monitor_web.models.scene_view import SceneModel, SceneViewModel, SceneViewOrderModel


def get_query_template_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 query 分类下的迁移 ORM 查询配置。

    这里放的都是带业务字段的查询相关表，因此统一直接按业务过滤：
    - ``QueryTemplate``
    - ``FavoriteGroup``
    - ``QueryHistory``
    - ``SceneModel``
    - ``SceneViewModel``
    - ``SceneViewOrderModel``

    ``FavoriteGroup`` 的组间排序配置实际落在 ``ApplicationConfig``，
    那部分已经由 ``internal_config`` 负责，这里只处理查询对象本身。
    """
    filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    return [
        (QueryTemplate, filters, None),
        (FavoriteGroup, filters, None),
        (QueryHistory, filters, None),
        (SceneModel, filters, None),
        (SceneViewModel, filters, None),
        (SceneViewOrderModel, filters, None),
    ]
