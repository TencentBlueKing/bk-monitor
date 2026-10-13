from unittest.mock import patch

import pytest

from bk_monitor_base.infras.third_party_api.unify_query.api import (
    get_dimension_data,
    promql_to_struct,
    query_data_by_promql,
    struct_to_promql,
)


class TestPromqlToStruct:
    """测试 PromQL 转结构化查询参数"""

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.promql_to_struct_client")
    def test_promql_to_struct_success(self, mock_client):
        """测试成功转换 PromQL 到结构化查询"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        promql = 'up{job="prometheus"}'
        expected_data = {
            "query_list": [
                {
                    "data_source": "prometheus",
                    "table_id": "up",
                    "field_name": "value",
                    "where": [{"key": "job", "method": "eq", "value": ["prometheus"]}],
                }
            ]
        }

        # 模拟客户端返回
        mock_client.return_value = {"data": expected_data}

        # 执行测试
        result = promql_to_struct(bk_tenant_id=bk_tenant_id, promql=promql)

        # 验证结果
        assert result == expected_data
        mock_client.assert_called_once_with(bk_tenant_id=bk_tenant_id, params={"promql": promql})

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.promql_to_struct_client")
    def test_promql_to_struct_with_complex_query(self, mock_client):
        """测试复杂 PromQL 查询的转换"""
        bk_tenant_id = "test_tenant"
        promql = 'rate(http_requests_total{job="api-server"}[5m])'
        expected_data = {
            "query_list": [
                {
                    "data_source": "prometheus",
                    "table_id": "http_requests_total",
                    "field_name": "value",
                    "function": [{"method": "rate", "dimensions": [], "window": "5m"}],
                    "where": [{"key": "job", "method": "eq", "value": ["api-server"]}],
                }
            ]
        }

        mock_client.return_value = {"data": expected_data}

        result = promql_to_struct(bk_tenant_id=bk_tenant_id, promql=promql)

        assert result == expected_data
        mock_client.assert_called_once_with(bk_tenant_id=bk_tenant_id, params={"promql": promql})


class TestStructToPromql:
    """测试结构化查询参数转 PromQL"""

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.struct_to_promql_client")
    def test_struct_to_promql_success(self, mock_client):
        """测试成功转换结构化查询到 PromQL"""
        bk_tenant_id = "test_tenant"
        params = {
            "query_list": [
                {
                    "data_source": "prometheus",
                    "table_id": "up",
                    "field_name": "value",
                    "where": [{"key": "job", "method": "eq", "value": ["prometheus"]}],
                }
            ],
            "metric_merge": "sum",
            "order_by": None,
            "step": "1m",
            "space_uid": None,
        }
        expected_response = 'sum(up{job="prometheus"})'

        # 模拟客户端返回字典格式，包含 data.promql 字段
        mock_client.return_value = {"data": {"promql": expected_response}}

        result = struct_to_promql(bk_tenant_id=bk_tenant_id, params=params)

        assert result == expected_response
        mock_client.assert_called_once_with(bk_tenant_id=bk_tenant_id, params=params)

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.struct_to_promql_client")
    def test_struct_to_promql_with_aggregation(self, mock_client):
        """测试带聚合函数的转换"""
        bk_tenant_id = "test_tenant"
        params = {
            "query_list": [
                {
                    "data_source": "prometheus",
                    "table_id": "http_requests_total",
                    "field_name": "value",
                    "function": [{"method": "rate", "dimensions": [], "window": "5m"}],
                }
            ],
            "metric_merge": "avg",
            "order_by": ["-value"],
            "step": "30s",
            "space_uid": "bkcc__2",
        }
        expected_response = "avg(rate(http_requests_total[5m]))"

        # 模拟客户端返回字典格式，包含 data.promql 字段
        mock_client.return_value = {"data": {"promql": expected_response}}

        result = struct_to_promql(bk_tenant_id=bk_tenant_id, params=params)

        assert result == expected_response
        mock_client.assert_called_once_with(bk_tenant_id=bk_tenant_id, params=params)


class TestQueryDataByPromql:
    """测试使用 PromQL 查询数据"""

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.query_data_by_promql_client")
    def test_query_data_by_promql_basic(self, mock_client):
        """测试基本的 PromQL 查询"""
        bk_tenant_id = "test_tenant"
        promql = 'up{job="prometheus"}'
        start = "1640000000"
        end = "1640003600"

        expected_response = {
            "series": [
                {
                    "name": "_result0",
                    "metric_name": "up",
                    "columns": ["_time", "_value"],
                    "types": ["float", "float"],
                    "group_keys": ["job"],
                    "group_values": ["prometheus"],
                    "values": [[1640000000000, 1], [1640000060000, 1]],
                }
            ]
        }

        mock_client.return_value = expected_response

        result = query_data_by_promql(bk_tenant_id=bk_tenant_id, promql=promql, start=start, end=end)

        assert result == expected_response
        mock_client.assert_called_once()
        call_args = mock_client.call_args
        assert call_args[1]["bk_tenant_id"] == bk_tenant_id
        assert call_args[1]["params"]["promql"] == promql
        assert call_args[1]["params"]["start"] == start
        assert call_args[1]["params"]["end"] == end

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.query_data_by_promql_client")
    def test_query_data_by_promql_with_step(self, mock_client):
        """测试带步长的 PromQL 查询"""
        bk_tenant_id = "test_tenant"
        promql = "rate(http_requests_total[5m])"
        start = "1640000000"
        end = "1640003600"
        step = "30s"

        mock_client.return_value = {"series": []}

        result = query_data_by_promql(bk_tenant_id=bk_tenant_id, promql=promql, start=start, end=end, step=step)  # noqa: F841

        mock_client.assert_called_once()
        call_args = mock_client.call_args
        assert call_args[1]["params"]["step"] == step

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.query_data_by_promql_client")
    def test_query_data_by_promql_with_all_params(self, mock_client):
        """测试带所有可选参数的 PromQL 查询"""
        bk_tenant_id = "test_tenant"
        promql = "up"
        start = "1640000000"
        end = "1640003600"
        match = "job"
        is_verify_dimensions = True
        bk_biz_ids = ["2", "3"]
        step = "1m"
        timezone = "Asia/Shanghai"
        down_sample_range = "5m"
        reference = True

        mock_client.return_value = {"series": []}

        result = query_data_by_promql(  # noqa: F841
            bk_tenant_id=bk_tenant_id,
            promql=promql,
            start=start,
            end=end,
            match=match,
            is_verify_dimensions=is_verify_dimensions,
            bk_biz_ids=bk_biz_ids,
            step=step,
            timezone=timezone,
            down_sample_range=down_sample_range,
            reference=reference,
        )

        mock_client.assert_called_once()
        call_args = mock_client.call_args
        params = call_args[1]["params"]
        assert params["match"] == match
        assert params["is_verify_dimensions"] == is_verify_dimensions
        assert params["bk_biz_ids"] == bk_biz_ids
        assert params["step"] == step
        assert params["timezone"] == timezone
        assert params["down_sample_range"] == down_sample_range
        assert params["reference"] == reference

    def test_query_data_by_promql_invalid_step_format(self):
        """测试无效的步长格式"""
        bk_tenant_id = "test_tenant"
        promql = "up"
        start = "1640000000"
        end = "1640003600"
        invalid_step = "invalid"

        with pytest.raises(ValueError) as exc_info:
            query_data_by_promql(
                bk_tenant_id=bk_tenant_id,
                promql=promql,
                start=start,
                end=end,
                step=invalid_step,
            )

        assert "Invalid step format" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    @pytest.mark.parametrize(
        "step",
        ["30s", "1m", "5m", "1h", "1d", "1w", "1y", "100ms"],
    )
    def test_query_data_by_promql_valid_step_formats(self, step):
        """测试各种有效的步长格式"""
        with patch("bk_monitor_base.infras.third_party_api.unify_query.api.query_data_by_promql_client") as mock_client:
            mock_client.return_value = {"series": []}

            result = query_data_by_promql(
                bk_tenant_id="test_tenant",
                promql="up",
                start="1640000000",
                end="1640003600",
                step=step,
            )

            # 验证没有抛出异常
            assert result == {"series": []}


class TestGetDimensionData:
    """测试获取维度数据"""

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.get_dimension_data_client")
    def test_get_dimension_data_basic(self, mock_client):
        """测试基本的维度数据查询"""
        bk_tenant_id = "test_tenant"
        params = {"info_type": "field"}

        expected_data = {
            "fields": [
                {"field_name": "bk_target_ip", "field_type": "string"},
                {"field_name": "bk_target_cloud_id", "field_type": "string"},
            ]
        }

        mock_client.return_value = {"data": expected_data}

        result = get_dimension_data(bk_tenant_id=bk_tenant_id, params=params)

        assert result == expected_data
        mock_client.assert_called_once()
        call_args = mock_client.call_args
        assert call_args[1]["bk_tenant_id"] == bk_tenant_id
        assert call_args[1]["params"]["info_type"] == "field"

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.get_dimension_data_client")
    def test_get_dimension_data_with_table_id(self, mock_client):
        """测试带表ID的维度数据查询"""
        bk_tenant_id = "test_tenant"
        params = {"info_type": "field", "table_id": "system.cpu_summary"}

        expected_data = {
            "fields": [
                {"field_name": "usage", "field_type": "float"},
                {"field_name": "idle", "field_type": "float"},
            ]
        }

        mock_client.return_value = {"data": expected_data}

        result = get_dimension_data(bk_tenant_id=bk_tenant_id, params=params)

        assert result == expected_data
        call_args = mock_client.call_args
        assert call_args[1]["params"]["table_id"] == "system.cpu_summary"

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.get_dimension_data_client")
    def test_get_dimension_data_with_conditions(self, mock_client):
        """测试带查询条件的维度数据查询"""
        bk_tenant_id = "test_tenant"
        params = {
            "info_type": "dimension_values",
            "conditions": {"field_name": "bk_target_ip"},
            "keys": ["bk_target_ip"],
        }

        expected_data = {"values": ["127.0.0.1", "192.168.1.1"]}

        mock_client.return_value = {"data": expected_data}

        result = get_dimension_data(bk_tenant_id=bk_tenant_id, params=params)

        assert result == expected_data
        call_args = mock_client.call_args
        assert call_args[1]["params"]["conditions"] == {"field_name": "bk_target_ip"}
        assert call_args[1]["params"]["keys"] == ["bk_target_ip"]

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.get_dimension_data_client")
    def test_get_dimension_data_with_all_params(self, mock_client):
        """测试带所有参数的维度数据查询"""
        bk_tenant_id = "test_tenant"
        params = {
            "info_type": "dimension_values",
            "space_uid": "bkcc__2",
            "table_id": "system.cpu_summary",
            "conditions": {"field_name": "usage"},
            "keys": ["bk_target_ip", "bk_target_cloud_id"],
            "limit": 500,
            "metric_name": "cpu_usage",
            "start_time": "1640000000",
            "end_time": "1640003600",
        }

        expected_data = {"values": ["value1", "value2"]}

        mock_client.return_value = {"data": expected_data}

        result = get_dimension_data(bk_tenant_id=bk_tenant_id, params=params)

        assert result == expected_data
        call_args = mock_client.call_args
        result_params = call_args[1]["params"]
        assert result_params["space_uid"] == "bkcc__2"
        assert result_params["table_id"] == "system.cpu_summary"
        assert result_params["conditions"] == {"field_name": "usage"}
        assert result_params["keys"] == ["bk_target_ip", "bk_target_cloud_id"]
        assert result_params["limit"] == 500
        assert result_params["metric_name"] == "cpu_usage"
        assert result_params["start_time"] == "1640000000"
        assert result_params["end_time"] == "1640003600"

    @patch("bk_monitor_base.infras.third_party_api.unify_query.api.get_dimension_data_client")
    def test_get_dimension_data_minimal_params(self, mock_client):
        """测试只传必填参数的情况"""
        bk_tenant_id = "test_tenant"
        params = {"info_type": "field"}

        mock_client.return_value = {"data": {}}

        result = get_dimension_data(bk_tenant_id=bk_tenant_id, params=params)  # noqa: F841

        call_args = mock_client.call_args
        result_params = call_args[1]["params"]

        # 验证只有必填参数在请求中
        assert result_params["info_type"] == "field"
        # 验证可选参数不在请求中（如果用户没有传）
        assert len(result_params) == 1
