"""自定义指标协议专用查询接口测试。"""

from monitor_web.custom_report.resources.metric import QueryCustomTimeSeriesProtocols
from monitor_web.models.custom_report import CustomTSTable


def test_query_all_business_protocols_in_current_tenant(mocker):
    """全业务查询只返回当前租户的 Data ID 与协议字段。"""
    mocker.patch("monitor_web.custom_report.resources.metric.get_request_tenant_id", return_value="tenant-a")
    expected = [
        {"bk_data_id": 1001, "protocol": "json"},
        {"bk_data_id": 1002, "protocol": "prometheus"},
    ]
    queryset = mocker.Mock()
    queryset.order_by.return_value.values.return_value = expected
    filter_query = mocker.patch.object(CustomTSTable.objects, "filter", return_value=queryset)

    result = QueryCustomTimeSeriesProtocols().request(bk_biz_id=0, bk_data_ids=[])

    assert result == expected
    filter_query.assert_called_once_with(bk_tenant_id="tenant-a")
    queryset.filter.assert_not_called()
    queryset.order_by.assert_called_once_with("bk_data_id")
    queryset.order_by.return_value.values.assert_called_once_with("bk_data_id", "protocol")


def test_query_protocols_by_business_and_data_ids(mocker):
    """业务与批量 Data ID 条件应取交集。"""
    mocker.patch("monitor_web.custom_report.resources.metric.get_request_tenant_id", return_value="tenant-a")
    expected = [{"bk_data_id": 1002, "protocol": "prometheus"}]
    queryset = mocker.Mock()
    queryset.filter.return_value = queryset
    queryset.order_by.return_value.values.return_value = expected
    mocker.patch.object(CustomTSTable.objects, "filter", return_value=queryset)

    result = QueryCustomTimeSeriesProtocols().request(bk_biz_id=2, bk_data_ids=[1002, 1003, 9999])

    assert result == expected
    assert queryset.filter.call_args_list == [
        mocker.call(bk_biz_id=2),
        mocker.call(bk_data_id__in=[1002, 1003, 9999]),
    ]
