from django.db.models import QuerySet

from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)


def _get_collect_config_queryset(bk_biz_id: int | None) -> QuerySet[CollectConfigMeta]:
    """
    获取采集配置根查询集。

    采集配置不存在合法的全局业务数据，因此始终排除 ``bk_biz_id=0``。
    """
    queryset = CollectConfigMeta.objects.exclude(bk_biz_id=0)
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    return queryset


def get_collect_config_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取采集配置迁移所需的 ORM 查询配置。

    仅返回采集配置链：
    - ``CollectConfigMeta`` 主表
    - ``DeploymentConfigVersion`` 部署配置表
    """
    collect_config_queryset = _get_collect_config_queryset(bk_biz_id)
    collect_config_ids = collect_config_queryset.values_list("id", flat=True)
    collect_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}

    return [
        (DeploymentConfigVersion, {"config_meta_id__in": collect_config_ids}, None),
        (CollectConfigMeta, collect_filters, {"bk_biz_id": 0}),
    ]


def get_collector_plugin_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取业务下的插件定义链。

    ``CollectorPluginMeta`` 本身就带有 ``bk_biz_id``，因此插件主表直接按业务过滤。
    然后再基于这批插件的 ``plugin_id`` 回查版本表，以及版本依赖的 config/info。
    """
    plugin_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    plugin_queryset = CollectorPluginMeta.objects.filter(**(plugin_filters or {}))
    plugin_ids = plugin_queryset.values_list("plugin_id", flat=True)
    plugin_versions = PluginVersionHistory.objects.filter(plugin_id__in=plugin_ids)

    plugin_config_ids = plugin_versions.values_list("config_id", flat=True)
    plugin_info_ids = plugin_versions.values_list("info_id", flat=True)

    return [
        (CollectorPluginMeta, plugin_filters, None),
        (CollectorPluginConfig, {"id__in": plugin_config_ids}, None),
        (CollectorPluginInfo, {"id__in": plugin_info_ids}, None),
        (PluginVersionHistory, {"plugin_id__in": plugin_ids}, None),
    ]
