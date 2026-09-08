"""测试 BkApiClient 的 batch_request 方法"""

import json
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class MockApiClient(BkApiClient):
    """测试用的 API Client"""

    abstract_class: ClassVar[bool] = False
    module_name: ClassVar[str] = "test"
    action: ClassVar[str] = "test_action"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = "test/"
    apigw_path: ClassVar[str] = "test/"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/test/"
    apigw_base_url: ClassVar[str] = "api/bk-test/prod/"


class MockPostApiClient(MockApiClient):
    """测试用的 POST API Client（用于验证 JSON body 的 nested 分页参数写入）"""

    method: ClassVar[str] = "POST"


# 测试辅助函数和 fixture


@pytest.fixture
def mock_admin_user():
    """Mock 租户管理员用户名"""
    with patch(
        "bk_monitor_base.infras.third_party_api.user.api.get_tenant_admin_username",
        return_value="admin",
    ):
        yield


class BatchRequestMockHelper:
    """批量请求测试的 Mock 辅助类"""

    BASE_URL = "http://bkapi.example.com/api/c/compapi/v2/test/test/"

    def __init__(self, requests_mock):
        """初始化 Mock 辅助类

        Args:
            requests_mock: requests_mock 的 mocker 对象
        """
        self.requests_mock = requests_mock

    def mock_first_request(
        self,
        total: int,
        batch_size: int = 500,
        custom_data_list: list[dict[str, Any]] | None = None,
        page_or_offset_key: str = "page",
        page_size_or_limit_key: str = "page_size",
        total_key: str = "total",
        data_list_key: str = "list",
        additional_params: dict[str, Any] | None = None,
        status_code: int = 200,
        error_text: str | None = None,
        pagination_mode: str = "page",
        first_page_or_start_value: int = 1,
    ) -> None:
        """Mock 首次请求（同时返回第一页数据与总数）

        Args:
            total: 总记录数
            batch_size: 首次请求的分页大小（即 batch_request 的 batch_size）
            custom_data_list: 自定义首次请求返回的数据列表（不提供时会按 total/batch_size 自动生成）
            page_or_offset_key: 分页键名(page/offset)，默认为 "page"
            page_size_or_limit_key: 分页大小键名(page_size/limit)，默认为 "page_size"
            total_key: 总数键名，默认为 "total"
            data_list_key: 数据列表键名，默认为 "list"
            additional_params: 额外的请求参数
            status_code: HTTP 状态码，默认为 200
            error_text: 错误文本（用于模拟失败情况）
            pagination_mode: 分页模式，默认为 "page"
            first_page_or_start_value: 首次页码/起始 offset，默认为 1
        """
        pagination_mode = (pagination_mode or "").lower()
        if pagination_mode not in {"page", "offset"}:
            raise ValueError(f"unsupported pagination_mode: {pagination_mode}")

        # 构建 URL
        url = self._build_url(
            {page_or_offset_key: first_page_or_start_value, page_size_or_limit_key: batch_size},
            additional_params=additional_params,
        )

        if status_code != 200 or error_text:
            # 模拟失败情况
            self.requests_mock.get(url, status_code=status_code, text=error_text)
            return

        # 构建响应数据
        if custom_data_list is not None:
            data_list = custom_data_list
        else:
            if total <= 0:
                data_list = []
            else:
                if pagination_mode == "page":
                    start_id = 1
                    end_id = min(start_id + batch_size, total + 1)
                else:
                    # offset 模式：first_page_or_start_value 表示 offset
                    start_id = first_page_or_start_value + 1
                    end_id = min(start_id + batch_size, total + 1)
                data_list = [{"id": i} for i in range(start_id, end_id)]

        response_data = self._build_response_data(
            total=total,
            data_list=data_list,
            total_key=total_key,
            data_list_key=data_list_key,
        )

        self.requests_mock.get(url, json=response_data)

    def mock_page_request(
        self,
        index: int,
        batch_size: int,
        start_id: int,
        end_id: int,
        total: int,
        page_or_offset_key: str = "page",
        page_size_or_limit_key: str = "page_size",
        total_key: str = "total",
        data_list_key: str = "list",
        additional_params: dict[str, Any] | None = None,
        status_code: int = 200,
        error_text: str | None = None,
        custom_data_list: list[dict[str, Any]] | None = None,
    ) -> None:
        """Mock 分页请求

        Args:
            index: 页码或 offset
            batch_size: 分页大小
            start_id: 起始 ID（包含）
            end_id: 结束 ID（不包含）
            total: 总记录数
            page_or_offset_key: 分页键名，默认为 "page"
            page_size_or_limit_key: 分页大小键名，默认为 "page_size"
            total_key: 总数键名，默认为 "total"
            data_list_key: 数据列表键名，默认为 "list"
            additional_params: 额外的请求参数
            status_code: HTTP 状态码，默认为 200
            error_text: 错误文本（用于模拟失败情况）
            custom_data_list: 自定义数据列表，如果提供则忽略 start_id 和 end_id
        """
        # 构建 URL
        url = self._build_url(
            {page_or_offset_key: index, page_size_or_limit_key: batch_size},
            additional_params=additional_params,
        )

        if status_code != 200 or error_text:
            # 模拟失败情况
            self.requests_mock.get(url, status_code=status_code, text=error_text)
            return

        # 构建响应数据
        if custom_data_list is not None:
            data_list = custom_data_list
        else:
            data_list = [{"id": i} for i in range(start_id, end_id)]
        response_data = self._build_response_data(
            total=total,
            data_list=data_list,
            total_key=total_key,
            data_list_key=data_list_key,
        )

        self.requests_mock.get(url, json=response_data)

    def mock_paginated_requests(
        self,
        total: int,
        batch_size: int,
        page_or_offset_key: str = "page",
        page_size_or_limit_key: str = "page_size",
        total_key: str = "total",
        data_list_key: str = "list",
        additional_params: dict[str, Any] | None = None,
        failed_pages: list[int] | None = None,
        pagination_mode: str = "page",
        first_page_or_start_value: int = 1,
    ) -> None:
        """Mock 完整的分页请求序列

        Args:
            total: 总记录数
            batch_size: 分页大小
            page_or_offset_key: 分页键名，默认为 "page"
            page_size_or_limit_key: 分页大小键名，默认为 "page_size"
            total_key: 总数键名，默认为 "total"
            data_list_key: 数据列表键名，默认为 "list"
            additional_params: 额外的请求参数
            failed_pages: 失败的页码列表
            pagination_mode: 分页模式，默认为 "page"
            first_page_or_start_value: 首次页码/起始 offset，默认为 1
        """
        import math

        if failed_pages is None:
            failed_pages = []

        # Mock 首次请求
        self.mock_first_request(
            total=total,
            batch_size=batch_size,
            page_or_offset_key=page_or_offset_key,
            page_size_or_limit_key=page_size_or_limit_key,
            total_key=total_key,
            data_list_key=data_list_key,
            additional_params=additional_params,
            pagination_mode=pagination_mode,
            first_page_or_start_value=first_page_or_start_value,
        )

        # 计算总页数
        total_pages = math.ceil(total / batch_size)

        pagination_mode = (pagination_mode or "").lower()
        if pagination_mode not in {"page", "offset"}:
            raise ValueError(f"unsupported pagination_mode: {pagination_mode}")

        def _is_failed(index: int) -> bool:
            return index in failed_pages

        if pagination_mode == "page":
            indices = [first_page_or_start_value + i for i in range(total_pages)]
            # 首次请求已经返回第一页，这里跳过第一页避免重复注册相同 URL
            for page in indices[1:]:
                start_id = (page - first_page_or_start_value) * batch_size + 1
                end_id = min(start_id + batch_size, total + 1)
                if _is_failed(page):
                    self.mock_page_request(
                        index=page,
                        batch_size=batch_size,
                        start_id=start_id,
                        end_id=end_id,
                        total=total,
                        page_or_offset_key=page_or_offset_key,
                        page_size_or_limit_key=page_size_or_limit_key,
                        total_key=total_key,
                        data_list_key=data_list_key,
                        additional_params=additional_params,
                        status_code=500,
                        error_text="Internal Server Error",
                    )
                else:
                    self.mock_page_request(
                        index=page,
                        batch_size=batch_size,
                        start_id=start_id,
                        end_id=end_id,
                        total=total,
                        page_or_offset_key=page_or_offset_key,
                        page_size_or_limit_key=page_size_or_limit_key,
                        total_key=total_key,
                        data_list_key=data_list_key,
                        additional_params=additional_params,
                    )
        else:
            indices = [first_page_or_start_value + i * batch_size for i in range(total_pages)]
            # 首次请求已经返回第一页，这里跳过第一页避免重复注册相同 URL
            for offset in indices[1:]:
                start_id = offset + 1
                end_id = min(start_id + batch_size, total + 1)
                if _is_failed(offset):
                    self.mock_page_request(
                        index=offset,
                        batch_size=batch_size,
                        start_id=start_id,
                        end_id=end_id,
                        total=total,
                        page_or_offset_key=page_or_offset_key,
                        page_size_or_limit_key=page_size_or_limit_key,
                        total_key=total_key,
                        data_list_key=data_list_key,
                        additional_params=additional_params,
                        status_code=500,
                        error_text="Internal Server Error",
                    )
                else:
                    self.mock_page_request(
                        index=offset,
                        batch_size=batch_size,
                        start_id=start_id,
                        end_id=end_id,
                        total=total,
                        page_or_offset_key=page_or_offset_key,
                        page_size_or_limit_key=page_size_or_limit_key,
                        total_key=total_key,
                        data_list_key=data_list_key,
                        additional_params=additional_params,
                    )

    def _build_url(
        self,
        params: dict[str, Any],
        additional_params: dict[str, Any] | None = None,
    ) -> str:
        """构建请求 URL

        Args:
            params: 基本参数
            additional_params: 额外参数

        Returns:
            完整的 URL 字符串
        """
        all_params = dict(params)
        if additional_params:
            all_params.update(additional_params)

        # 构建查询字符串
        query_parts = [f"{k}={v}" for k, v in sorted(all_params.items())]
        query_string = "&".join(query_parts)

        return f"{self.BASE_URL}?{query_string}"

    def _build_response_data(
        self,
        total: int,
        data_list: list[dict[str, Any]],
        total_key: str = "total",
        data_list_key: str = "list",
    ) -> dict[str, Any]:
        """构建响应数据

        Args:
            total: 总记录数
            data_list: 数据列表
            total_key: 总数键名
            data_list_key: 数据列表键名

        Returns:
            响应数据字典
        """
        # 处理嵌套键（如 "data.total"）
        if "." in total_key or "." in data_list_key:
            # 使用嵌套结构
            result = {"result": True}
            self._set_nested_value(result, total_key, total)
            self._set_nested_value(result, data_list_key, data_list)
            return result
        else:
            # 使用扁平结构
            return {
                "result": True,
                total_key: total,
                data_list_key: data_list,
            }

    @staticmethod
    def _set_nested_value(data: dict[str, Any], key_path: str, value: Any) -> None:
        """设置嵌套字典的值

        Args:
            data: 目标字典
            key_path: 键路径（如 "data.total"）
            value: 要设置的值
        """
        keys = key_path.split(".")
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value


class TestBatchRequest:
    """batch_request 方法的测试用例"""

    def test_batch_request_single_page(self, requests_mock, mock_admin_user):
        """测试只有一页数据的情况"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=5, batch_size=10)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=10,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 5
        assert len(result) == 5
        assert result[0]["id"] == 1
        assert result[4]["id"] == 5

    def test_batch_request_multiple_pages(self, requests_mock, mock_admin_user):
        """测试多页数据的情况"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=25, batch_size=10)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=10,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 25
        assert len(result) == 25
        assert result[0]["id"] == 1
        assert result[24]["id"] == 25

    def test_batch_request_nested_page_keys_in_post_body(self, requests_mock, mock_admin_user):
        """测试 page_or_offset_key/page_size_or_limit_key 支持 nested（点号路径）写入到 POST JSON body。

        这里选择 POST 场景，是因为 GET 的 query params 对嵌套结构通常不会按预期编码；
        而对多数第三方 API 来说，nested 分页参数更多出现在 JSON body 中。
        """

        base_url = BatchRequestMockHelper.BASE_URL
        total = 25
        batch_size = 10
        total_key = "total"
        data_list_key = "list"

        page_or_offset_key = "pagination.page"
        page_size_or_limit_key = "pagination.page_size"

        def _build_payload(page: int) -> dict[str, Any]:
            return {"foo": "bar", "pagination": {"page": page, "page_size": batch_size}}

        def _build_response_data(data_list: list[dict[str, Any]]) -> dict[str, Any]:
            return {"result": True, total_key: total, data_list_key: data_list}

        def _matcher(expected_payload: dict[str, Any]):
            def _match(request) -> bool:
                try:
                    body = request.body.decode("utf-8") if isinstance(request.body, bytes | bytearray) else request.body
                    payload = json.loads(body)
                except Exception:
                    return False
                return payload == expected_payload

            return _match

        # 首次请求：page=1
        first_list = [{"id": i} for i in range(1, 11)]
        requests_mock.post(
            base_url,
            additional_matcher=_matcher(_build_payload(page=1)),
            json=_build_response_data(first_list),
        )

        # 后续分页：page=2,3（并发请求）
        page_2_list = [{"id": i} for i in range(11, 21)]
        page_3_list = [{"id": i} for i in range(21, 26)]
        requests_mock.post(
            base_url,
            additional_matcher=_matcher(_build_payload(page=2)),
            json=_build_response_data(page_2_list),
        )
        requests_mock.post(
            base_url,
            additional_matcher=_matcher(_build_payload(page=3)),
            json=_build_response_data(page_3_list),
        )

        client = MockPostApiClient()
        success, result, got_total = client.batch_request(
            bk_tenant_id="system",
            params={"foo": "bar"},
            batch_size=batch_size,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key=page_or_offset_key,
            page_size_or_limit_key=page_size_or_limit_key,
            total_key=total_key,
            data_list_key=data_list_key,
        )

        assert success is True
        assert got_total == total
        assert len(result) == total
        assert result[0]["id"] == 1
        assert result[-1]["id"] == 25

    def test_batch_request_with_limit(self, requests_mock, mock_admin_user):
        """测试使用 limit 限制返回数量"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=100, batch_size=10)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=10,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
            total_limit=15,
        )

        assert success is True
        assert total == 100
        assert len(result) == 15
        assert result[0]["id"] == 1
        assert result[14]["id"] == 15

    def test_batch_request_zero_total(self, requests_mock, mock_admin_user):
        """测试总数为0的情况"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_first_request(total=0)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 0
        assert result == []

    def test_batch_request_empty_list(self, requests_mock, mock_admin_user):
        """测试返回空列表的情况"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_first_request(total=0)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 0
        assert result == []

    def test_batch_request_exact_page_size(self, requests_mock, mock_admin_user):
        """测试总数正好等于分页大小的情况"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=10, batch_size=10)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=10,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 10
        assert len(result) == 10
        assert result[0]["id"] == 1
        assert result[9]["id"] == 10

    def test_batch_request_custom_keys(self, requests_mock, mock_admin_user):
        """测试自定义分页键名和数据键名"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_first_request(
            total=5,
            batch_size=10,
            page_or_offset_key="page_num",
            total_key="data.total",
            data_list_key="data.items",
        )

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page_num",
            page_size_or_limit_key="page_size",
            total_key="data.total",
            data_list_key="data.items",
            batch_size=10,
        )

        assert success is True
        assert total == 5
        assert len(result) == 5
        assert result[0]["id"] == 1

    def test_batch_request_custom_batch_size(self, requests_mock, mock_admin_user):
        """测试自定义分页大小"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=20, batch_size=5)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=5,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 20
        assert len(result) == 20

    def test_batch_request_custom_concurrent_count(self, requests_mock, mock_admin_user):
        """测试自定义并发数"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=30, batch_size=10)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=10,
            concurrent_count=2,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 30
        assert len(result) == 30

    def test_batch_request_first_request_fails(self, requests_mock, mock_admin_user):
        """测试首次请求失败的情况"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_first_request(
            total=0,
            status_code=500,
            error_text="Internal Server Error",
        )

        client = MockApiClient()
        with pytest.raises(Exception):
            client.batch_request(
                bk_tenant_id="system",
                params={},
                pagination_mode="page",
                first_page_or_start_value=1,
                page_or_offset_key="page",
                page_size_or_limit_key="page_size",
                total_key="total",
                data_list_key="list",
            )

    def test_batch_request_page_request_fails(self, requests_mock, mock_admin_user):
        """测试某个页面请求失败但不影响其他页面"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=30, batch_size=10, failed_pages=[3])

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=10,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
            ignore_partial_error=True,
        )

        # 应该包含第1页和第2页的数据（第3页失败）
        assert success is False
        assert total == 30
        assert len(result) == 20  # 10 + 10
        assert result[0]["id"] == 1
        assert result[10]["id"] == 11

    def test_batch_request_nested_keys(self, requests_mock, mock_admin_user):
        """测试使用嵌套键路径（如 'data.list'）提取数据"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(
            total=5,
            batch_size=10,
            total_key="data.total",
            data_list_key="data.list",
        )

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="data.total",
            data_list_key="data.list",
            batch_size=10,
        )

        assert success is True
        assert total == 5
        assert len(result) == 5
        assert result[0]["id"] == 1

    def test_batch_request_with_user_params(self, requests_mock):
        """测试使用自定义用户参数"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(total=3, batch_size=10)

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            user_params={"bk_username": "test_user"},
            params={},
            batch_size=10,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 3
        assert len(result) == 3

    def test_batch_request_with_additional_params(self, requests_mock, mock_admin_user):
        """测试使用额外的请求参数"""
        helper = BatchRequestMockHelper(requests_mock)
        # Mock 首次请求
        helper.mock_first_request(
            total=2,
            batch_size=10,
            additional_params={"filter": "active"},
            custom_data_list=[
                {"id": 1, "status": "active"},
                {"id": 2, "status": "active"},
            ],
        )

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={"filter": "active"},
            batch_size=10,
            pagination_mode="page",
            first_page_or_start_value=1,
            page_or_offset_key="page",
            page_size_or_limit_key="page_size",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 2
        assert len(result) == 2
        assert result[0]["status"] == "active"

    def test_batch_request_offset_mode(self, requests_mock, mock_admin_user):
        """测试 offset/limit 分页模式的情况"""
        helper = BatchRequestMockHelper(requests_mock)
        helper.mock_paginated_requests(
            total=25,
            batch_size=10,
            page_or_offset_key="offset",
            page_size_or_limit_key="limit",
            pagination_mode="offset",
            first_page_or_start_value=0,
        )

        client = MockApiClient()
        success, result, total = client.batch_request(
            bk_tenant_id="system",
            params={},
            batch_size=10,
            pagination_mode="offset",
            first_page_or_start_value=0,
            page_or_offset_key="offset",
            page_size_or_limit_key="limit",
            total_key="total",
            data_list_key="list",
        )

        assert success is True
        assert total == 25
        assert len(result) == 25
        assert result[0]["id"] == 1
        assert result[24]["id"] == 25
