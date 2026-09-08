import requests_mock

from bk_monitor_base.infras.third_party_api.log_search.api import (
    fetch_statistics_graph,
    fetch_statistics_info,
    fetch_topk_list,
    list_es_router,
)


def test_list_es_router():
    """测试获取Es的结果表"""

    response_payload = {
        "result": True,
        "data": {
            "list": [
                {
                    "cluster_id": 3,
                    "data_label": "bklog_index_set_109",
                    "index_set": "2_bklog_test_1",
                    "need_create_index": False,
                    "options": [
                        {
                            "name": "time_field",
                            "value": '{"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"}',
                            "value_type": "dict",
                        },
                        {"name": "need_add_time", "value": "true", "value_type": "bool"},
                    ],
                    "origin_table_id": "2_bklog.test_1",
                    "source_type": "log",
                    "space_uid": "bkcc__2",
                    "table_id": "bklog_index_set_109_2_bklog_test_1.__default__",
                }
            ],
            "total": 67,
        },
    }

    with requests_mock.Mocker() as m:
        m.get(
            "http://bkapi.example.com/api/c/compapi/v2/bk_log/index_set/list_es_router/",
            json=response_payload,
        )

        data = list_es_router(bk_tenant_id="system", space_uid="bkcc__2", page=2, pagesize=50)

        # 返回结构校验
        assert "list" in data
        assert "total" in data
        assert data["total"] == 67
        assert len(data["list"]) == 1
        assert data["list"][0]["cluster_id"] == 3

        # 请求参数拼装校验
        last_request = m.last_request
        assert last_request is not None
        assert last_request.method == "GET"
        assert last_request.qs == {"page": ["2"], "pagesize": ["50"], "space_uid": ["bkcc__2"]}


def test_fetch_statistics_info():
    """
    测试获取字段统计信息
    """
    with requests_mock.Mocker() as m:
        m.post(
            "http://bkapi.example.com/api/c/compapi/v2/bk_log/field/index_set/statistics/info/",
            json={
                "result": True,
                "data": {
                    "total_count": 1053250,
                    "distinct_count": 1,
                    "field_count": 1053250,
                    "field_percent": 1.0,
                    "value_analysis": {"max": 0.0, "min": 0.0, "avg": 0.0, "median": 0.0},
                },
            },
        )

        response = fetch_statistics_info(bk_tenant_id="system", params={"index_set_ids": [1]})
        assert response["total_count"] == 1053250


def test_fetch_statistics_graph():
    """
    测试获取字段统计图表
    """
    with requests_mock.Mocker() as m:
        m.post(
            "http://bkapi.example.com/api/c/compapi/v2/bk_log/field/index_set/statistics/graph/",
            json={
                "result": True,
                "data": {
                    "series": [
                        {
                            "name": "_result0",
                            "metric_name": "",
                            "columns": ["_time", "_value"],
                            "types": ["float", "float"],
                            "group_keys": ["serverIp"],
                            "group_values": ["10.10.28.20"],
                            "values": [[1769097600000, 44], [1769184000000, 0]],
                        },
                    ],
                },
            },
        )

        response = fetch_statistics_graph(bk_tenant_id="system", params={"index_set_ids": [1]})
        assert len(response["series"]) == 1
        assert len(response["series"][0]["values"]) == 2


def test_fetch_topk_list():
    """
    测试获取字段topk计数列表
    """
    with requests_mock.Mocker() as m:
        m.post(
            "http://bkapi.example.com/api/c/compapi/v2/bk_log/field/index_set/fetch_topk_list/",
            json={
                "result": True,
                "data": {
                    "name": "levelname",
                    "columns": ["_value", "_count"],
                    "types": ["float", "float"],
                    "limit": 50,
                    "total_count": 838572,
                    "field_count": 838572,
                    "distinct_count": 5,
                    "values": [["INFO", 486604], ["WARNING", 221616], ["ERROR", 130350], ["CRITICAL", 2], ["", 0]],
                },
            },
        )

        response = fetch_topk_list(bk_tenant_id="system", params={"index_set_ids": [1]})
        assert len(response["values"]) == 5
        assert response["distinct_count"] == 5
