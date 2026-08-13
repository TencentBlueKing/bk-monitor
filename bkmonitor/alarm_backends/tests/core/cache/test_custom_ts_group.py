"""自定义指标协议缓存测试。"""

from types import SimpleNamespace

import pytest

from alarm_backends.core.cache.models.custom_ts_group import CustomTSGroupCacheManager
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata.models import TimeSeriesGroup


def make_ts_group(
    bk_data_id: int,
    bk_tenant_id: str = "tenant-a",
    bk_biz_id: int = 2,
    builtin: bool = False,
) -> SimpleNamespace:
    """构造缓存测试需要的时序分组。"""
    return SimpleNamespace(
        bk_data_id=bk_data_id,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        time_series_group_id=bk_data_id + 10000,
        time_series_group_name=f"group_{bk_data_id}",
        is_cmdb_relation_builtin=lambda: builtin,
    )


def test_get_queries_protocol_with_tenant_on_cache_miss(mocker):
    """缓存 miss 时应从 TimeSeriesGroup 反查租户并调用专用接口。"""
    cache = mocker.Mock()
    cache.get.return_value = None
    mocker.patch.object(CustomTSGroupCacheManager, "cache", cache)
    ts_group = make_ts_group(1001)
    mocker.patch.object(TimeSeriesGroup.objects, "get", return_value=ts_group)
    query_protocols = mocker.patch.object(
        api.monitor,
        "query_custom_time_series_protocols",
        return_value=[{"bk_data_id": 1001, "protocol": "prometheus"}],
    )

    protocol = CustomTSGroupCacheManager.get(1001)

    assert protocol == "prometheus"
    query_protocols.assert_called_once_with(
        bk_tenant_id="tenant-a",
        bk_data_ids=[1001],
    )
    cache.set.assert_called_once_with(CustomTSGroupCacheManager.format_key(1001), "prometheus")


@pytest.mark.parametrize(
    ("builtin", "expected_protocol"),
    [
        (False, "json"),
        (True, "prometheus"),
    ],
)
def test_get_keeps_protocol_fallback_for_missing_monitor_record(mocker, builtin, expected_protocol):
    """monitor_web 无记录时应保留普通与 CMDB 内置时序的差异化协议判定。"""
    cache = mocker.Mock()
    cache.get.return_value = None
    mocker.patch.object(CustomTSGroupCacheManager, "cache", cache)
    mocker.patch.object(TimeSeriesGroup.objects, "get", return_value=make_ts_group(1001, builtin=builtin))
    mocker.patch.object(api.monitor, "query_custom_time_series_protocols", return_value=[])

    assert CustomTSGroupCacheManager.get(1001) == expected_protocol
    cache.set.assert_called_once_with(CustomTSGroupCacheManager.format_key(1001), expected_protocol)


def test_get_falls_back_to_detail_when_new_api_is_unavailable(mocker):
    """专用接口未发布或暂时异常时，应兼容使用原详情接口。"""
    cache = mocker.Mock()
    cache.get.return_value = None
    mocker.patch.object(CustomTSGroupCacheManager, "cache", cache)
    mocker.patch.object(TimeSeriesGroup.objects, "get", return_value=make_ts_group(1001))
    mocker.patch.object(
        api.monitor,
        "query_custom_time_series_protocols",
        side_effect=BKAPIError(system_name="monitor", url="query_protocols", result={"message": "unavailable"}),
    )
    detail = mocker.patch.object(api.metadata, "custom_time_series_detail", return_value={"protocol": "prometheus"})

    assert CustomTSGroupCacheManager.get(1001) == "prometheus"
    detail.assert_called_once_with(
        bk_tenant_id="tenant-a",
        time_series_group_id=11001,
        bk_biz_id=2,
        model_only=True,
        empty_if_not_found=True,
    )


def test_refresh_batches_by_tenant_and_preserves_failed_tenant_cache(mocker):
    """刷新应按租户批量查询，失败租户不覆盖已有缓存。"""
    groups = [
        make_ts_group(1001, builtin=False),
        make_ts_group(1002, builtin=True),
        make_ts_group(2001, bk_tenant_id="tenant-b", builtin=False),
    ]
    queryset = mocker.Mock()
    queryset.only.return_value = groups
    filter_groups = mocker.patch.object(TimeSeriesGroup.objects, "filter", return_value=queryset)

    cache = mocker.Mock()
    pipeline = cache.pipeline.return_value
    mocker.patch.object(CustomTSGroupCacheManager, "cache", cache)

    def query_protocols(**kwargs):
        if kwargs["bk_tenant_id"] == "tenant-b":
            raise BKAPIError(
                system_name="monitor",
                url="query_protocols",
                result={"message": "tenant-b unavailable"},
            )
        return [{"bk_data_id": 1001, "protocol": "prometheus"}]

    query_api = mocker.patch.object(api.monitor, "query_custom_time_series_protocols", side_effect=query_protocols)

    CustomTSGroupCacheManager.refresh()

    filter_groups.assert_called_once_with(is_delete=False)
    assert query_api.call_count == 2
    query_api.assert_any_call(bk_tenant_id="tenant-a", bk_biz_id=0, bk_data_ids=[])
    query_api.assert_any_call(bk_tenant_id="tenant-b", bk_biz_id=0, bk_data_ids=[])
    pipeline.set.assert_any_call(CustomTSGroupCacheManager.format_key(1001), "prometheus")
    pipeline.set.assert_any_call(CustomTSGroupCacheManager.format_key(1002), "prometheus")
    assert mocker.call(CustomTSGroupCacheManager.format_key(2001), "json") not in pipeline.set.call_args_list
    pipeline.delete.assert_not_called()
    pipeline.execute.assert_called_once_with()


def test_refresh_propagates_unexpected_error(mocker):
    """刷新时非接口异常应直接暴露，避免被误判为租户刷新失败。"""
    queryset = mocker.Mock()
    queryset.only.return_value = [make_ts_group(1001)]
    mocker.patch.object(TimeSeriesGroup.objects, "filter", return_value=queryset)

    cache = mocker.Mock()
    mocker.patch.object(CustomTSGroupCacheManager, "cache", cache)
    mocker.patch.object(
        api.monitor,
        "query_custom_time_series_protocols",
        side_effect=KeyError("unexpected response"),
    )

    with pytest.raises(KeyError, match="unexpected response"):
        CustomTSGroupCacheManager.refresh()

    cache.pipeline.return_value.execute.assert_not_called()
