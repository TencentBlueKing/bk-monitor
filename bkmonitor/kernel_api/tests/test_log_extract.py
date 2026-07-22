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
            SearchLogExtractFilesResource,
            "list_log_extract_files",
            {
                "bk_biz_id": 7,
                "ip_list": [{"bk_host_id": 101}],
                "path": "/data/logs",
                "is_search_child": False,
                "time_range": "1d",
            },
            [{"path": "/data/logs/app.log"}],
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


def test_get_download_url_passes_through(monkeypatch):
    api_resource = Mock(return_value="https://example.com/download")
    monkeypatch.setattr(api.log_search, "get_log_extract_download_url", api_resource)

    result = GetLogExtractDownloadUrlResource().perform_request({"bk_biz_id": 7, "task_id": 123})

    assert result == "https://example.com/download"
    api_resource.assert_called_once_with(bk_biz_id=7, task_id=123, is_url="1")
