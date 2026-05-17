from datetime import datetime
from types import SimpleNamespace

import pytest

from bk_monitor_base.metric_plugin import VersionTuple
from monitor_web.collecting.constant import TaskStatus
from monitor_web.collecting.resources.new.backend import CollectConfigListResource


def _make_deployment(
    deployment_id: int,
    *,
    name: str,
    status: str,
    subscription_id: int | None = None,
    bk_biz_id: int = 2,
    plugin_id: str = "test_plugin",
):
    related_params = {}
    if subscription_id is not None:
        related_params["subscription_id"] = subscription_id
    return SimpleNamespace(
        id=deployment_id,
        name=name,
        bk_biz_id=bk_biz_id,
        plugin_id=plugin_id,
        status=status,
        updated_at=datetime(2025, 1, 1, 0, 0, 0),
        updated_by="admin",
        related_params=related_params,
    )


def _make_version() -> SimpleNamespace:
    return SimpleNamespace(
        plugin_version=VersionTuple(major=1, minor=0),
        target_scope=SimpleNamespace(node_type="INSTANCE", nodes=[{"bk_host_id": 1}]),
        params={},
    )


def _make_plugin(*, plugin_type: str = "script", version: VersionTuple | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="test_plugin",
        type=plugin_type,
        name="Test Plugin",
        label="component",
        version=version or VersionTuple(major=1, minor=1),
    )


@pytest.mark.parametrize(
    ("search_dict", "expected_statuses"),
    [
        ({"status": "STARTED"}, ["running"]),
        ({"status": "STOPPED"}, ["stopped"]),
        ({"status": "STARTING"}, ["starting"]),
        ({"status": "STOPPING"}, ["stopping"]),
        ({"status": "DEPLOYING"}, ["deploying"]),
        ({"status": "PREPARING"}, ["initializing"]),
        ({"task_status": TaskStatus.PREPARING}, ["initializing"]),
        ({"task_status": TaskStatus.DEPLOYING}, ["deploying"]),
        ({"task_status": TaskStatus.STARTING}, ["starting"]),
        ({"task_status": TaskStatus.STOPPING}, ["stopping"]),
        ({"task_status": TaskStatus.STOPPED}, ["stopped"]),
    ],
)
def test_collect_config_list_build_base_query_kwargs_translates_status(search_dict, expected_statuses):
    kwargs, terminal_task_status, need_memory_filter, need_memory_order = (
        CollectConfigListResource._build_base_query_kwargs(
            bk_biz_ids=[2],
            search_dict=search_dict,
            order=None,
            page=1,
            limit=10,
        )
    )

    assert kwargs["deployment_statuses"] == expected_statuses
    assert terminal_task_status is None
    assert need_memory_filter is False
    assert need_memory_order is False
    assert kwargs["limit"] == 10
    assert kwargs["offset"] == 0


def test_collect_config_list_terminal_task_status_filters_in_memory(mocker):
    deployment_running_failed = _make_deployment(1, name="running-failed", status="running", subscription_id=101)
    deployment_running_success = _make_deployment(2, name="running-success", status="running", subscription_id=102)
    deployment_failed = _make_deployment(3, name="failed", status="failed", subscription_id=103)
    version = _make_version()
    plugin = _make_plugin()

    mocker.patch("monitor_web.collecting.resources.new.backend._ensure_tenant_id", return_value="tenant")
    mocker.patch(
        "monitor_web.collecting.resources.new.backend.list_metric_plugin_deployments",
        return_value=([deployment_running_failed, deployment_running_success, deployment_failed], 3),
    )
    mocker.patch(
        "monitor_web.collecting.resources.new.backend.get_metric_plugin_deployment",
        side_effect=[
            (deployment_running_failed, version),
            (deployment_running_success, version),
            (deployment_failed, version),
        ],
    )
    mocker.patch("monitor_web.collecting.resources.new.backend._get_plugin", return_value=plugin)
    mocker.patch(
        "monitor_web.collecting.resources.new.backend.SpaceApi.list_spaces",
        return_value=[SimpleNamespace(bk_biz_id=2, space_name="业务A", type_name="业务")],
    )
    mocker.patch("monitor_web.collecting.resources.new.backend.get_request", return_value=None)
    mocker.patch(
        "monitor_web.collecting.resources.new.backend.api.node_man.fetch_subscription_statistic.bulk_request",
        return_value=[
            [
                {"subscription_id": 101, "instances": 3, "status": [{"status": "FAILED", "count": 3}]},
                {"subscription_id": 102, "instances": 3, "status": [{"status": "SUCCESS", "count": 3}]},
                {"subscription_id": 103, "instances": 1, "status": [{"status": "SUCCESS", "count": 1}]},
            ]
        ],
    )

    result = CollectConfigListResource().perform_request(
        {
            "page": 1,
            "limit": 10,
            "search": {"task_status": TaskStatus.FAILED},
        }
    )

    assert result["total"] == 2
    assert [item["id"] for item in result["config_list"]] == [1, 3]


def test_collect_config_list_pushes_fuzzy_status_order_and_page_to_base(mocker):
    deployment = _make_deployment(2, name="beta", status="running", subscription_id=201)
    version = _make_version()
    plugin = _make_plugin()

    list_mock = mocker.patch(
        "monitor_web.collecting.resources.new.backend.list_metric_plugin_deployments",
        return_value=([deployment], 2),
    )
    mocker.patch("monitor_web.collecting.resources.new.backend._ensure_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.collecting.resources.new.backend.get_request", return_value=None)
    mocker.patch(
        "monitor_web.collecting.resources.new.backend.get_metric_plugin_deployment",
        return_value=(deployment, version),
    )
    mocker.patch("monitor_web.collecting.resources.new.backend._get_plugin", return_value=plugin)
    mocker.patch(
        "monitor_web.collecting.resources.new.backend.SpaceApi.list_spaces",
        return_value=[SimpleNamespace(bk_biz_id=2, space_name="业务A", type_name="业务")],
    )

    result = CollectConfigListResource().perform_request(
        {
            "page": 2,
            "limit": 1,
            "order": "-name",
            "search": {"fuzzy": "cpu", "status": "STARTED"},
        }
    )

    assert result["total"] == 2
    list_mock.assert_called_once_with(
        bk_tenant_id="tenant",
        bk_biz_ids=None,
        plugin_ids=None,
        deployment_statuses=["running"],
        fuzzy="cpu",
        order_by="name",
        order_desc=True,
        limit=1,
        offset=1,
    )
