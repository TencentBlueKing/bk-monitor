from unittest.mock import Mock

import pytest
from rest_framework import serializers

from core.drf_resource import api
from kernel_api.resource.log_extract import (
    CreateLogExtractTaskMCPResource,
    GetLogExtractTaskMCPResource,
    SearchLogExtractFilesResource,
    SearchLogExtractHostsResource,
)


def test_search_hosts_builds_scoped_exact_ip_query(monkeypatch):
    query_hosts = Mock(
        return_value={
            "total": 1,
            "data": [
                {
                    "host_id": 101,
                    "ip": "10.0.0.1",
                    "host_name": "app-1",
                    "cloud_area": {"id": 2, "name": "cloud-2"},
                    "alive": 1,
                }
            ],
        }
    )
    monkeypatch.setattr(api.log_extract, "query_log_extract_hosts", query_hosts)

    result = SearchLogExtractHostsResource().perform_request({"bk_biz_id": 7, "ip": "10.0.0.1"})

    assert result["resolution"] == "RESOLVED"
    assert result["hosts"][0]["bk_host_id"] == 101
    assert result["hosts"][0]["bk_cloud_id"] == 2
    query_hosts.assert_called_once_with(
        scope_list=[{"scope_type": "biz", "scope_id": "7"}],
        node_list=[{"object_id": "biz", "instance_id": 7}],
        search_condition={"ip": "10.0.0.1"},
        start=0,
        page_size=20,
    )


def test_search_files_limits_mcp_response(monkeypatch):
    list_files = Mock(return_value=[{"path": "/a"}, {"path": "/b"}, {"path": "/c"}])
    monkeypatch.setattr(api.log_extract, "list_log_extract_files", list_files)
    request_data = {
        "bk_biz_id": 7,
        "ip_list": [{"bk_host_id": 101, "ip": "10.0.0.1", "bk_cloud_id": 2}],
        "path": "/data/logs",
        "is_search_child": False,
        "time_range": "1d",
        "start_time": "",
        "end_time": "",
        "limit": 2,
    }

    result = SearchLogExtractFilesResource().perform_request(request_data)

    assert result == {"total": 3, "files": [{"path": "/a"}, {"path": "/b"}], "truncated": True}
    assert "limit" not in list_files.call_args.kwargs


def test_create_task_hides_link_and_fills_preview_fields(monkeypatch):
    create_task = Mock(return_value={"task_id": 123})
    monkeypatch.setattr(api.log_extract, "create_log_extract_task", create_task)
    request_data = {
        "bk_biz_id": 7,
        "ip_list": [{"bk_host_id": 101, "ip": "10.0.0.1", "bk_cloud_id": 2}],
        "file_path": ["/data/logs/app.log", "/data/logs/error.log"],
        "filter_type": "",
        "filter_content": {},
        "remark": "mcp",
    }

    result = CreateLogExtractTaskMCPResource().perform_request(request_data)

    assert result == {"task_id": 123, "status": "QUEUED", "poll_after_seconds": 5}
    payload = create_task.call_args.kwargs
    assert payload["preview_directory"] == "/data/logs"
    assert payload["preview_ip_list"] == [{"bk_host_id": 101, "ip": "10.0.0.1", "bk_cloud_id": 2}]
    assert "link_id" not in payload


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [("init", "QUEUED"), ("packing", "RUNNING"), ("downloadable", "SUCCEEDED"), ("failed", "FAILED")],
)
def test_get_task_normalizes_status(monkeypatch, raw_status, expected):
    monkeypatch.setattr(
        api.log_extract,
        "get_log_extract_task",
        Mock(return_value={"task_id": 123, "bk_biz_id": 7, "download_status": raw_status}),
    )

    result = GetLogExtractTaskMCPResource().perform_request({"bk_biz_id": 7, "task_id": 123})

    assert result["status"] == expected


def test_get_task_rejects_business_mismatch(monkeypatch):
    monkeypatch.setattr(
        api.log_extract,
        "get_log_extract_task",
        Mock(return_value={"task_id": 123, "bk_biz_id": 8, "download_status": "downloadable"}),
    )

    with pytest.raises(serializers.ValidationError):
        GetLogExtractTaskMCPResource().perform_request({"bk_biz_id": 7, "task_id": 123})
