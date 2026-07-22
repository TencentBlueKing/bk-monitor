from unittest.mock import Mock

import pytest

from core.drf_resource import api
from kernel_api.resource.log_extract import (
    CreateLogExtractTaskResource,
    GetLogExtractDownloadUrlResource,
    GetLogExtractTaskResource,
    ListLogExtractAllowedPathsResource,
    ListLogExtractTopologyResource,
    SearchLogExtractFilesResource,
    SearchLogExtractHostsResource,
)


@pytest.mark.parametrize(
    ("resource", "request_data"),
    [
        (ListLogExtractAllowedPathsResource, {"bk_biz_id": 7}),
        (ListLogExtractAllowedPathsResource, {"bk_biz_id": 7, "ip_list": [{}]}),
        (
            ListLogExtractAllowedPathsResource,
            {
                "bk_biz_id": 7,
                "target_node_type": "TOPO",
                "ip_list": [{"bk_host_id": 101}],
            },
        ),
        (
            ListLogExtractAllowedPathsResource,
            {
                "bk_biz_id": 7,
                "target_node_type": "INSTANCE",
                "target_nodes": [{"object_id": "module", "instance_id": 42}],
            },
        ),
        (
            CreateLogExtractTaskResource,
            {
                "bk_biz_id": 7,
                "file_path": ["/data/logs/app.log"],
                "filter_type": "",
                "filter_content": {},
            },
        ),
        (
            CreateLogExtractTaskResource,
            {
                "bk_biz_id": 7,
                "ip_list": [{}],
                "file_path": ["/data/logs/app.log"],
                "filter_type": "",
                "filter_content": {},
            },
        ),
    ],
)
def test_target_request_serializer_rejects_invalid_selection(resource, request_data):
    serializer = resource.RequestSerializer(data=request_data)

    assert not serializer.is_valid()


@pytest.mark.parametrize(
    "request_data",
    [
        {"bk_biz_id": 7, "ip_list": [{"bk_host_id": 101}]},
        {"bk_biz_id": 7, "ip_list": [{"ip": "10.0.0.1", "bk_cloud_id": 0}]},
        {
            "bk_biz_id": 7,
            "target_node_type": "INSTANCE",
            "target_nodes": [{"object_id": "host", "instance_id": 101}],
        },
        {
            "bk_biz_id": 7,
            "target_node_type": "TOPO",
            "target_nodes": [{"object_id": "module", "instance_id": 42}],
        },
        {
            "bk_biz_id": 7,
            "target_node_type": "SERVICE_TEMPLATE",
            "target_nodes": [{"object_id": "SERVICE_TEMPLATE", "instance_id": 42}],
        },
    ],
)
def test_allowed_paths_request_serializer_accepts_valid_selection(request_data):
    serializer = ListLogExtractAllowedPathsResource.RequestSerializer(data=request_data)

    assert serializer.is_valid(), serializer.errors


def test_search_files_request_serializer_rejects_incomplete_ip():
    serializer = SearchLogExtractFilesResource.RequestSerializer(
        data={
            "bk_biz_id": 7,
            "ip_list": [{"ip": "10.0.0.1"}],
            "path": "/data/logs",
            "is_search_child": False,
            "time_range": "1d",
        }
    )

    assert not serializer.is_valid()
    assert "ip_list" in serializer.errors


@pytest.mark.parametrize(
    ("request_data", "expected_request"),
    [
        (
            {"bk_biz_id": 7, "ip_list": [{"bk_host_id": 101}]},
            {"bk_biz_id": 7, "ip_list": [{"bk_host_id": 101}]},
        ),
        (
            {
                "bk_biz_id": 7,
                "target_node_type": "TOPO",
                "target_nodes": [{"object_id": "module", "instance_id": 42}],
            },
            {
                "bk_biz_id": 7,
                "target_node_type": "TOPO",
                "target_nodes": [{"bk_obj_id": "module", "bk_inst_id": 42}],
            },
        ),
    ],
)
def test_list_allowed_paths_builds_request(monkeypatch, request_data, expected_request):
    strategies = [{"file_path": "/data/logs", "file_type": ["log"]}]
    response = {"ip_list": [{"bk_host_id": 101}], "strategies": strategies}
    api_resource = Mock(return_value=response)
    monkeypatch.setattr(api.log_search, "list_log_extract_allowed_paths", api_resource)

    result = ListLogExtractAllowedPathsResource().perform_request(request_data)

    assert result == response
    api_resource.assert_called_once_with(**expected_request)


def test_list_topology_builds_business_scope(monkeypatch):
    api_resource = Mock(return_value=[])
    monkeypatch.setattr(api.log_search, "list_log_extract_topology", api_resource)

    result = ListLogExtractTopologyResource().perform_request({"bk_biz_id": 7})

    assert result == []
    api_resource.assert_called_once_with(scope_list=[{"scope_type": "biz", "scope_id": "7"}])


def test_search_hosts_builds_business_scope_and_defaults_to_business_root(monkeypatch):
    response = {"total": 1, "data": [{"host_id": 101, "cloud_id": 0, "ip": "10.0.0.1"}]}
    api_resource = Mock(return_value=response)
    monkeypatch.setattr(api.log_search, "query_log_extract_hosts", api_resource)

    result = SearchLogExtractHostsResource().perform_request(
        {"bk_biz_id": 7, "search_content": "10.0.0.1", "start": 0, "page_size": 20}
    )

    assert result["data"][0]["bk_host_id"] == 101
    assert result["data"][0]["bk_cloud_id"] == 0
    api_resource.assert_called_once_with(
        scope_list=[{"scope_type": "biz", "scope_id": "7"}],
        node_list=[{"object_id": "biz", "instance_id": 7}],
        search_content="10.0.0.1",
        start=0,
        page_size=20,
    )


def test_search_hosts_keeps_selected_nodes(monkeypatch):
    api_resource = Mock(return_value={"total": 0, "data": []})
    monkeypatch.setattr(api.log_search, "query_log_extract_hosts", api_resource)
    node_list = [{"object_id": "module", "instance_id": 42}]

    SearchLogExtractHostsResource().perform_request({"bk_biz_id": 7, "node_list": node_list})

    api_resource.assert_called_once_with(scope_list=[{"scope_type": "biz", "scope_id": "7"}], node_list=node_list)


def test_search_files_limits_returned_records(monkeypatch):
    files = [{"path": f"/data/logs/{index}.log"} for index in range(101)]
    api_resource = Mock(return_value=files)
    monkeypatch.setattr(api.log_search, "list_log_extract_files", api_resource)
    request_data = {
        "bk_biz_id": 7,
        "ip_list": [{"bk_host_id": 101}],
        "path": "/data/logs",
        "is_search_child": False,
        "time_range": "1d",
    }

    result = SearchLogExtractFilesResource().perform_request(request_data)

    assert result == {"total": 101, "data": files[:100], "truncated": True}
    api_resource.assert_called_once_with(**request_data)


def test_create_task_translates_nodes_and_defaults_preview_metadata(monkeypatch):
    api_resource = Mock(return_value={"task_id": 123})
    monkeypatch.setattr(api.log_search, "create_log_extract_task", api_resource)
    request_data = {
        "bk_biz_id": 7,
        "target_node_type": "TOPO",
        "target_nodes": [{"object_id": "module", "instance_id": 42}],
        "file_path": ["/data/logs/app.log"],
        "filter_type": "",
        "filter_content": {},
    }

    result = CreateLogExtractTaskResource().perform_request(request_data)

    assert result == {"task_id": 123}
    api_resource.assert_called_once_with(
        bk_biz_id=7,
        target_node_type="TOPO",
        target_nodes=[{"bk_obj_id": "module", "bk_inst_id": 42}],
        file_path=["/data/logs/app.log"],
        filter_type="",
        filter_content={},
        preview_directory="/data/logs",
        preview_ip_list=[],
        preview_time_range="all",
        preview_is_search_child=False,
    )


@pytest.mark.parametrize(
    ("raw_state", "process_info", "state", "terminal", "downloadable", "error"),
    [
        ("init", None, "pending", False, False, None),
        ("packing", None, "running", False, False, None),
        ("downloadable", None, "downloadable", True, True, None),
        ("failed", "packing failed", "failed", True, False, "packing failed"),
        ("expired", None, "expired", True, False, None),
        ("new_status", None, "unknown", True, False, "Unsupported BK Log task status: new_status"),
    ],
)
def test_get_task_normalizes_polling_state(monkeypatch, raw_state, process_info, state, terminal, downloadable, error):
    api_resource = Mock(
        return_value={
            "task_id": 123,
            "bk_biz_id": 7,
            "download_status": raw_state,
            "task_process_info": process_info,
        }
    )
    monkeypatch.setattr(api.log_search, "get_log_extract_task", api_resource)

    result = GetLogExtractTaskResource().perform_request({"bk_biz_id": 7, "task_id": 123})

    assert result == {
        "task_id": 123,
        "bk_biz_id": 7,
        "state": state,
        "raw_state": raw_state,
        "terminal": terminal,
        "downloadable": downloadable,
        "error": error,
    }
    api_resource.assert_called_once_with(bk_biz_id=7, task_id=123)


def test_get_download_url_passes_through(monkeypatch):
    api_resource = Mock(return_value="https://example.com/download")
    monkeypatch.setattr(api.log_search, "get_log_extract_download_url", api_resource)

    result = GetLogExtractDownloadUrlResource().perform_request({"bk_biz_id": 7, "task_id": 123})

    assert result == "https://example.com/download"
    api_resource.assert_called_once_with(bk_biz_id=7, task_id=123, is_url="1")
