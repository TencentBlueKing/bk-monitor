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
    ("resource_class", "api_name", "request_data", "response"),
    [
        (
            ListLogExtractAllowedPathsResource,
            "list_log_extract_allowed_paths",
            {"bk_biz_id": 7, "ip_list": [{"bk_host_id": 101}]},
            {"ip_list": [{"bk_host_id": 101}], "strategies": [{"visible_dir": "/data/logs"}]},
        ),
        (
            CreateLogExtractTaskResource,
            "create_log_extract_task",
            {
                "bk_biz_id": 7,
                "ip_list": [{"bk_host_id": 101}],
                "file_path": ["/data/logs/app.log"],
                "filter_type": "",
                "filter_content": {},
                "preview_directory": "/data/logs",
                "preview_ip_list": [{"bk_host_id": 101}],
                "preview_time_range": "1d",
                "preview_is_search_child": False,
                "link_id": 1,
            },
            {"task_id": 123},
        ),
        (
            GetLogExtractTaskResource,
            "get_log_extract_task",
            {"bk_biz_id": 7, "task_id": 123},
            {"task_id": 123, "bk_biz_id": 7, "download_status": "downloadable"},
        ),
    ],
)
def test_log_extract_resource_passes_through(monkeypatch, resource_class, api_name, request_data, response):
    api_resource = Mock(return_value=response)
    monkeypatch.setattr(api.log_search, api_name, api_resource)

    result = resource_class().perform_request(request_data)

    assert result == response
    api_resource.assert_called_once_with(**request_data)


def test_list_topology_builds_business_scope(monkeypatch):
    api_resource = Mock(return_value=[])
    monkeypatch.setattr(api.log_search, "list_log_extract_topology", api_resource)

    result = ListLogExtractTopologyResource().perform_request({"bk_biz_id": 7})

    assert result == []
    api_resource.assert_called_once_with(scope_list=[{"scope_type": "biz", "scope_id": "7"}])


def test_list_allowed_paths_passes_through_topology_nodes(monkeypatch):
    response = {"ip_list": [{"bk_host_id": 101}], "strategies": [{"visible_dir": "/data/logs"}]}
    api_resource = Mock(return_value=response)
    monkeypatch.setattr(api.log_search, "list_log_extract_allowed_paths", api_resource)
    request_data = {
        "bk_biz_id": 7,
        "target_node_type": "TOPO",
        "target_nodes": [{"bk_obj_id": "module", "bk_inst_id": 42}],
    }

    result = ListLogExtractAllowedPathsResource().perform_request(request_data)

    assert result == response
    api_resource.assert_called_once_with(**request_data)


def test_search_hosts_builds_business_scope_and_defaults_to_business_root(monkeypatch):
    response = {"total": 1, "data": [{"host_id": 101, "ip": "10.0.0.1"}]}
    api_resource = Mock(return_value=response)
    monkeypatch.setattr(api.log_search, "query_log_extract_hosts", api_resource)

    result = SearchLogExtractHostsResource().perform_request(
        {"bk_biz_id": 7, "search_content": "10.0.0.1", "start": 0, "page_size": 20}
    )

    assert result == response
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


def test_search_hosts_defaults_to_twenty_and_rejects_unlimited_page_size():
    default_serializer = SearchLogExtractHostsResource.RequestSerializer(data={"bk_biz_id": 7})
    unlimited_serializer = SearchLogExtractHostsResource.RequestSerializer(data={"bk_biz_id": 7, "page_size": -1})

    assert default_serializer.is_valid()
    assert default_serializer.validated_data["page_size"] == 20
    assert not unlimited_serializer.is_valid()
    assert "page_size" in unlimited_serializer.errors


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


def test_search_files_rejects_more_than_ten_hosts():
    serializer = SearchLogExtractFilesResource.RequestSerializer(
        data={
            "bk_biz_id": 7,
            "ip_list": [{"bk_host_id": host_id} for host_id in range(11)],
            "path": "/data/logs",
            "is_search_child": False,
            "time_range": "1d",
        }
    )

    assert not serializer.is_valid()
    assert "ip_list" in serializer.errors


def test_get_download_url_passes_through(monkeypatch):
    api_resource = Mock(return_value="https://example.com/download")
    monkeypatch.setattr(api.log_search, "get_log_extract_download_url", api_resource)

    result = GetLogExtractDownloadUrlResource().perform_request({"bk_biz_id": 7, "task_id": 123})

    assert result == "https://example.com/download"
    api_resource.assert_called_once_with(bk_biz_id=7, task_id=123, is_url="1")
