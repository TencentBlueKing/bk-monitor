"""验证 APM 接入页上报地址的顺序、格式和配置容错。"""

import pytest
from bk_monitor_base.infras.nodeman_control.v3 import V3HostQueries
from django.test import override_settings

from apm_web.meta.resources import PushUrlResource
from bkmonitor.utils.custom_report_tools import custom_report_tool
from constants.apm import FormatType


def _mock_push_url_dependencies(mocker, proxy_hosts=None):
    """隔离节点管理和云区域查询，只验证地址组装逻辑。"""
    mocker.patch("apm_web.meta.resources.host_queries.business_proxies", return_value=proxy_hosts or [])
    mocker.patch.object(PushUrlResource, "_get_cloud_alias_map", return_value={1: "云一区"})


@pytest.mark.parametrize("advertise_ip_v6,expected", [("", "http://127.0.0.1"), ("::1", "http://[::1]")])
def test_v3_multi_ip_proxy_produces_single_report_address(mocker, advertise_ip_v6, expected):
    """原生 V3 多 IP 响应经过能力转换后，仍生成单个可用的上报地址。"""
    request = mocker.Mock(
        side_effect=[
            {"bk_networkarea_id": [1]},
            {
                "total": 1,
                "items": [
                    {
                        "bk_host_id": 1,
                        "info": {
                            "bk_biz_id": 2,
                            "bk_networkarea_id": 1,
                            "bk_host_innerip_list": ["127.0.0.1", "127.0.0.2"],
                            "bk_host_innerip_v6_list": ["::1", "::2"],
                            "advertise_ip_v6": advertise_ip_v6,
                        },
                    }
                ],
            },
        ]
    )
    _mock_push_url_dependencies(mocker)
    mocker.patch(
        "apm_web.meta.resources.host_queries.business_proxies",
        side_effect=lambda bk_biz_id: V3HostQueries(request).business_proxies("tenant", bk_biz_id),
    )
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=[], CUSTOM_REPORT_DEFAULT_PROXY_IP=[], CUSTOM_REPORT_ENDPOINTS=[]
    ):
        endpoints = PushUrlResource().perform_request({"bk_biz_id": 2, "format_type": FormatType.SIMPLE})
    assert [item["push_url"] for item in endpoints] == [expected]


@pytest.mark.parametrize(
    ("format_type", "expected_urls", "expected_aliases"),
    [
        (
            FormatType.DEFAULT,
            [
                "http://central.example:4317",
                "http://central.example:4318/v1/traces",
                "http://cluster-a.example:4317",
                "http://cluster-a.example:4318/v1/traces",
                "http://cluster-b.example:4317",
                "http://cluster-b.example:4318/v1/traces",
                "http://proxy.example:4317",
                "http://proxy.example:4318/v1/traces",
            ],
            ["内网", "内网", "集群 A", "集群 A", "集群 B", "集群 B", "云一区", "云一区"],
        ),
        (
            FormatType.SIMPLE,
            [
                "http://central.example",
                "http://cluster-a.example",
                "http://cluster-b.example",
                "http://proxy.example",
            ],
            ["内网", "集群 A", "集群 B", "云一区"],
        ),
    ],
)
def test_custom_report_endpoints_order_and_alias(mocker, format_type, expected_urls, expected_aliases):
    """中心化地址优先，配置地址按数组顺序排列，业务 Proxy 最后。"""
    _mock_push_url_dependencies(mocker, [{"inner_ip": "proxy.example", "bk_cloud_id": 1}])
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=["central.example"],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=["fallback.example"],
        CUSTOM_REPORT_ENDPOINTS=[
            {"endpoint": "cluster-a.example", "alias": "集群 A"},
            {"endpoint": "cluster-b.example", "alias": "集群 B"},
        ],
    ):
        endpoints = PushUrlResource().perform_request({"bk_biz_id": 2, "format_type": format_type})

    assert [item["push_url"] for item in endpoints] == expected_urls
    assert [item["bk_cloud_alias"] for item in endpoints] == expected_aliases
    proxy_count = 2 if format_type == FormatType.DEFAULT else 1
    assert [item["bk_cloud_id"] for item in endpoints] == [0] * (len(endpoints) - proxy_count) + [1] * proxy_count


def test_push_url_uses_proxy_ip_when_central_domain_is_empty(mocker):
    """中心化域名为空时，IP 地址仍排在配置地址之前。"""
    _mock_push_url_dependencies(mocker)
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=[],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=["127.0.0.1"],
        CUSTOM_REPORT_ENDPOINTS=[{"endpoint": "cluster.example", "alias": "集群"}],
    ):
        endpoints = PushUrlResource().perform_request({"bk_biz_id": 2, "format_type": FormatType.SIMPLE})

    assert [item["push_url"] for item in endpoints] == ["http://127.0.0.1", "http://cluster.example"]


def test_custom_report_endpoints_dedup_keeps_first_address_and_alias(mocker):
    """重复地址保留中心化配置及其别名，不让后续配置覆盖。"""
    _mock_push_url_dependencies(mocker, [{"inner_ip": "central.example", "bk_cloud_id": 0}])
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=["central.example"],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=[],
        CUSTOM_REPORT_ENDPOINTS=[
            {"endpoint": "central.example", "alias": "重复配置"},
            {"endpoint": "second.example", "alias": "第二项"},
        ],
    ):
        endpoints = PushUrlResource().perform_request({"bk_biz_id": 2, "format_type": FormatType.SIMPLE})

    assert [(item["push_url"], item["bk_cloud_alias"]) for item in endpoints] == [
        ("http://central.example", "内网"),
        ("http://second.example", "第二项"),
    ]


def test_custom_report_endpoints_skips_invalid_items(mocker):
    """非法条目不影响有效地址，也不触发接口异常。"""
    _mock_push_url_dependencies(mocker)
    warning = mocker.patch("apm_web.meta.resources.logger.warning")
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=[],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=[],
        CUSTOM_REPORT_ENDPOINTS=[
            "invalid",
            {"endpoint": "missing-alias.example"},
            {"endpoint": "valid.example", "alias": "有效地址"},
        ],
    ):
        endpoints = PushUrlResource().perform_request({"bk_biz_id": 2, "format_type": FormatType.SIMPLE})

    assert [(item["push_url"], item["bk_cloud_alias"]) for item in endpoints] == [("http://valid.example", "有效地址")]
    warning.assert_any_call("skip invalid CUSTOM_REPORT_ENDPOINTS item at index 0")
    warning.assert_any_call("skip invalid CUSTOM_REPORT_ENDPOINTS item at index 1")


def test_custom_report_endpoints_skips_non_list_config(mocker):
    """整个配置类型错误时返回空地址列表，不按字符串逐字符解析。"""
    _mock_push_url_dependencies(mocker)
    warning = mocker.patch("apm_web.meta.resources.logger.warning")
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=[],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=[],
        CUSTOM_REPORT_ENDPOINTS="invalid",
    ):
        endpoints = PushUrlResource().perform_request({"bk_biz_id": 2, "format_type": FormatType.SIMPLE})

    assert endpoints == []
    warning.assert_called_once_with("CUSTOM_REPORT_ENDPOINTS must be a list")


def test_push_url_ignores_removed_cluster_service_settings(mocker):
    """已删除的单域名和旧列表配置都不参与地址生成。"""
    _mock_push_url_dependencies(mocker)
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=[],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=[],
        CUSTOM_REPORT_ENDPOINTS=[],
        CUSTOM_REPORT_DEFAULT_K8S_CLUSTER_SERVICE="legacy.example",
        CUSTOM_REPORT_DEFAULT_K8S_CLUSTER_SERVICE_CONFIGS=[{"endpoint": "legacy-list.example", "alias": "旧配置"}],
    ):
        endpoints = PushUrlResource().perform_request({"bk_biz_id": 2, "format_type": FormatType.SIMPLE})

    assert endpoints == []


def test_background_report_uses_first_valid_endpoint(mocker):
    """首项无效时，后台上报改用后续第一个有效地址。"""
    post = mocker.patch("bkmonitor.utils.custom_report_tools.requests.post")
    post.return_value.status_code = 200
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=[],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=[],
        CUSTOM_REPORT_ENDPOINTS=[
            "invalid",
            {"endpoint": "missing-alias.example"},
            {"endpoint": "valid.example", "alias": "有效地址"},
        ],
    ):
        custom_report_tool(1).send_data_by_http([{"metrics": {"count": 1}}], "token", parallel=False)

    assert post.call_args.args[0] == "http://valid.example:10205/v2/push/"


def test_background_report_rejects_invalid_endpoints_without_central_proxy():
    """没有中心化地址和有效配置地址时，返回明确的配置错误。"""
    with override_settings(
        CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN=[],
        CUSTOM_REPORT_DEFAULT_PROXY_IP=[],
        CUSTOM_REPORT_ENDPOINTS=["invalid", {"endpoint": "missing-alias.example"}],
    ):
        with pytest.raises(ValueError, match="CUSTOM_REPORT_ENDPOINTS"):
            custom_report_tool(1).send_data_by_http([{"metrics": {"count": 1}}], "token", parallel=False)
