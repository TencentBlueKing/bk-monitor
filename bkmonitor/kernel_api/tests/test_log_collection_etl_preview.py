from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.log_search.default import LogEtlPreviewResource
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from constants.log_collection import (
    ETL_PREVIEW_MAX_EXPRESSION_LENGTH,
    ETL_PREVIEW_MAX_FIELDS,
    ETL_PREVIEW_MAX_SAMPLE_LENGTH,
    ETL_PREVIEW_MAX_SEPARATOR_LENGTH,
)
from core.drf_resource import api
from core.errors.api import BKAPIError
from kernel_api.resource.log_collection_etl_preview import PreviewLogEtlResource
from kernel_api.views.v4.log_collection_etl_preview import (
    EtlPreviewBusinessActionPermission,
    LogCollectionEtlPreviewViewSet,
)


@pytest.mark.parametrize(
    ("request_data", "bklog_response", "expected_fields"),
    [
        (
            {
                "bk_biz_id": 2,
                "etl_config": "bk_log_text",
                "data": "plain log",
            },
            {"fields": "plain log"},
            [{"field_index": 1, "field_name": "log", "value": "plain log"}],
        ),
        (
            {
                "bk_biz_id": 2,
                "etl_config": "bk_log_json",
                "data": '{"level":"INFO","code":200}',
            },
            {
                "fields": [
                    {"field_name": "level", "value": "INFO"},
                    {"field_name": "code", "value": 200},
                ]
            },
            [
                {"field_index": 1, "field_name": "level", "value": "INFO"},
                {"field_index": 2, "field_name": "code", "value": 200},
            ],
        ),
        (
            {
                "bk_biz_id": 2,
                "etl_config": "bk_log_regexp",
                "etl_params": {"separator_regexp": r"(?P<level>\w+):(?P<message>.*)"},
                "data": "INFO:started",
            },
            {
                "fields": [
                    {"field_index": 8, "field_name": "level", "value": "INFO"},
                    {"field_index": 9, "field_name": "message", "value": "started"},
                ]
            },
            [
                {"field_index": 1, "field_name": "level", "value": "INFO"},
                {"field_index": 2, "field_name": "message", "value": "started"},
            ],
        ),
        (
            {
                "bk_biz_id": 2,
                "etl_config": "bk_log_delimiter",
                "etl_params": {"separator": "|"},
                "data": "INFO|started",
            },
            {
                "fields": [
                    {"field_index": 1, "field_name": "", "value": "INFO"},
                    {"field_index": 2, "field_name": "", "value": "started"},
                ]
            },
            [
                {"field_index": 1, "field_name": "", "value": "INFO"},
                {"field_index": 2, "field_name": "", "value": "started"},
            ],
        ),
    ],
)
def test_preview_supported_etl_types(monkeypatch, request_data, bklog_response, expected_fields):
    api_resource = Mock(return_value=bklog_response)
    monkeypatch.setattr(api.log_search, "log_etl_preview", api_resource)

    result = PreviewLogEtlResource().request(request_data)

    assert result == {
        "success": True,
        "etl_config": request_data["etl_config"],
        "fields": expected_fields,
        "field_count": len(expected_fields),
        "error": None,
    }
    expected_request = {
        "bk_biz_id": request_data["bk_biz_id"],
        "etl_config": request_data["etl_config"],
        "etl_params": request_data.get("etl_params", {}),
        "data": request_data["data"],
    }
    api_resource.assert_called_once_with(**expected_request)


@pytest.mark.parametrize(
    "request_data",
    [
        {"bk_biz_id": 2, "etl_config": "custom", "data": "log"},
        {"bk_biz_id": 2, "etl_config": "bk_log_regexp", "data": "log"},
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_text",
            "etl_params": {"separator": "|"},
            "data": "log",
        },
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_json",
            "etl_params": {"template_id": 1},
            "data": "{}",
        },
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_json",
            "clean_template_id": 1,
            "data": "{}",
        },
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_text",
            "data": "x" * (ETL_PREVIEW_MAX_SAMPLE_LENGTH + 1),
        },
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_regexp",
            "etl_params": {"separator_regexp": "x" * (ETL_PREVIEW_MAX_EXPRESSION_LENGTH + 1)},
            "data": "log",
        },
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_regexp",
            "etl_params": {"separator_regexp": "("},
            "data": "log",
        },
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_regexp",
            "etl_params": {
                "separator_regexp": "".join(f"(?P<field_{index}>x)" for index in range(ETL_PREVIEW_MAX_FIELDS + 1))
            },
            "data": "x" * (ETL_PREVIEW_MAX_FIELDS + 1),
        },
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_delimiter",
            "etl_params": {"separator": "x" * (ETL_PREVIEW_MAX_SEPARATOR_LENGTH + 1)},
            "data": "log",
        },
    ],
)
def test_invalid_request_returns_unified_failure_without_calling_bklog(monkeypatch, request_data):
    api_resource = Mock()
    monkeypatch.setattr(api.log_search, "log_etl_preview", api_resource)

    result = PreviewLogEtlResource().request(request_data)

    assert result["success"] is False
    assert result["fields"] == []
    assert result["field_count"] == 0
    assert result["error"]["code"] == "invalid_request"
    assert result["error"]["details"]
    assert set(result) == {"success", "etl_config", "fields", "field_count", "error"}
    api_resource.assert_not_called()


def test_delimiter_field_limit_is_checked_before_calling_bklog(monkeypatch):
    api_resource = Mock()
    monkeypatch.setattr(api.log_search, "log_etl_preview", api_resource)
    data = "|".join(str(index) for index in range(ETL_PREVIEW_MAX_FIELDS + 1))

    result = PreviewLogEtlResource().request(
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_delimiter",
            "etl_params": {"separator": "|"},
            "data": data,
        }
    )

    assert result["success"] is False
    assert result["error"] == {
        "code": "too_many_fields",
        "message": f"ETL preview supports at most {ETL_PREVIEW_MAX_FIELDS} fields.",
        "details": {"field_count": ETL_PREVIEW_MAX_FIELDS + 1},
    }
    api_resource.assert_not_called()


def test_backend_field_limit_rejects_json_result(monkeypatch):
    api_resource = Mock(
        return_value={
            "fields": [{"field_name": f"field_{index}", "value": index} for index in range(ETL_PREVIEW_MAX_FIELDS + 1)]
        }
    )
    monkeypatch.setattr(api.log_search, "log_etl_preview", api_resource)

    result = PreviewLogEtlResource().request(
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_json",
            "data": "{}",
        }
    )

    assert result["success"] is False
    assert result["fields"] == []
    assert result["error"]["code"] == "too_many_fields"
    assert result["error"]["details"] == {"field_count": ETL_PREVIEW_MAX_FIELDS + 1}
    api_resource.assert_called_once()


@pytest.mark.parametrize(
    ("backend_code", "message"),
    [
        ("3631303", "字段提取预览失败，请检查提取规则与数据是否匹配"),
        ("3600914", "Grok 模式不存在：UNKNOWN_PATTERN"),
    ],
)
def test_bklog_validation_error_returns_unified_failure(monkeypatch, backend_code, message):
    api_resource = Mock(
        side_effect=BKAPIError(
            system_name="bk_log",
            url="/databus/clean_template/etl_preview/",
            result={"code": backend_code, "message": message},
        )
    )
    monkeypatch.setattr(api.log_search, "log_etl_preview", api_resource)

    result = PreviewLogEtlResource().request(
        {
            "bk_biz_id": 2,
            "etl_config": "bk_log_regexp",
            "etl_params": {"separator_regexp": "%{UNKNOWN_PATTERN:level}", "is_grok": True},
            "data": "123",
        }
    )

    assert result == {
        "success": False,
        "etl_config": "bk_log_regexp",
        "fields": [],
        "field_count": 0,
        "error": {
            "code": "invalid_etl_config",
            "message": message,
            "details": {"backend_code": backend_code},
        },
    }


def test_non_validation_bklog_error_is_not_hidden(monkeypatch):
    monkeypatch.setattr(
        api.log_search,
        "log_etl_preview",
        Mock(
            side_effect=BKAPIError(
                system_name="bk_log",
                url="/databus/clean_template/etl_preview/",
                result={"code": "500", "message": "upstream unavailable"},
            )
        ),
    )

    with pytest.raises(BKAPIError):
        PreviewLogEtlResource().request(
            {
                "bk_biz_id": 2,
                "etl_config": "bk_log_text",
                "data": "plain log",
            }
        )


def test_kernel_reuses_common_bklog_preview_api_resource():
    assert PreviewLogEtlResource.RequestSerializer is LogEtlPreviewResource.RequestSerializer
    assert LogEtlPreviewResource.action == "/databus/clean_template/etl_preview/"
    assert LogEtlPreviewResource.method == "POST"
    assert LogEtlPreviewResource.INSERT_BK_USERNAME_TO_REQUEST_DATA is True


def test_permission_rejects_query_and_body_business_mismatch(monkeypatch):
    base_permission = Mock(return_value=True)
    monkeypatch.setattr(BusinessActionPermission, "has_permission", base_permission)
    request = SimpleNamespace(
        data={"bk_biz_id": 2},
        query_params={"bk_biz_id": "3"},
        biz_id="3",
    )

    allowed = EtlPreviewBusinessActionPermission([]).has_permission(request, None)

    assert allowed is False
    base_permission.assert_not_called()


def test_permission_uses_body_business_for_iam_check(monkeypatch):
    base_permission = Mock(return_value=True)
    monkeypatch.setattr(BusinessActionPermission, "has_permission", base_permission)
    request = SimpleNamespace(
        data={"bk_biz_id": 2},
        query_params={},
        biz_id="2",
    )
    permission = EtlPreviewBusinessActionPermission([])

    allowed = permission.has_permission(request, None)

    assert allowed is True
    assert request.biz_id == 2
    base_permission.assert_called_once_with(request, None)


def test_etl_preview_view_requires_log_collection_mcp_permission():
    permissions = LogCollectionEtlPreviewViewSet().get_permissions()

    assert len(permissions) == 1
    assert permissions[0].actions[0].id == ActionEnum.USING_LOG_COLLECTION_MCP.id
