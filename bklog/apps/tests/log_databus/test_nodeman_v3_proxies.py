"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.log_databus.nodeman_v3.exceptions import NodeManV3APIError
from apps.log_databus.nodeman_v3.proxies import get_host_biz_proxies
from apps.log_databus.views.collector_views import CollectorViewSet


def host(host_id, area_id=3, **info):
    return {
        "bk_host_id": host_id,
        "info": {"bk_biz_id": 2, "bk_networkarea_id": area_id, **info},
    }


class BizProxiesTest(SimpleTestCase):
    def setUp(self):
        client_patch = patch("apps.log_databus.nodeman_v3.proxies.get_client")
        self.get_client = client_patch.start()
        self.addCleanup(client_patch.stop)
        self.client = self.get_client.return_value

    def test_queries_business_proxies_in_one_request(self):
        self.client.list_hosts.return_value = {
            "total": 3,
            "items": [
                host(10, advertise_ip="127.0.0.1"),
                host(11, area_id=7, advertise_ip="127.0.0.2"),
                host(14, area_id=0, advertise_ip="127.0.0.2"),
            ],
        }

        self.assertEqual(
            get_host_biz_proxies(2),
            [{"bk_cloud_id": 3, "conn_ip": "127.0.0.1"}, {"bk_cloud_id": 7, "conn_ip": "127.0.0.2"}],
        )
        self.get_client.assert_called_once_with(2)
        self.client.list_hosts.assert_called_once_with(
            {
                "page": {"offset": 0, "limit": 1000},
                "exact_include_conditions": {"bk_biz_id": [2], "node_role": ["proxy"]},
            }
        )

    def test_service_addresses_take_priority_and_ipv6_is_bracketed(self):
        self.client.list_hosts.return_value = {
            "total": 6,
            "items": [
                host(10, advertise_ip="127.0.0.1", advertise_ip_v6="2001:db8::10"),
                host(11, advertise_ip_v6="2001:db8::11", bk_host_innerip_list=["127.0.0.2"]),
                host(12, bk_host_innerip_list=["", "127.0.0.3"]),
                host(13, bk_host_innerip_v6_list=["2001:db8::13"]),
                host(14, export_ip="127.0.0.2", login_ip="127.0.0.3"),
                host(15, advertise_ip=" ", bk_host_innerip_list=[" 127.0.0.3 "]),
            ],
        }

        self.assertEqual(
            get_host_biz_proxies(2),
            [
                {"bk_cloud_id": 3, "conn_ip": "127.0.0.1"},
                {"bk_cloud_id": 3, "conn_ip": "[2001:db8::11]"},
                {"bk_cloud_id": 3, "conn_ip": "127.0.0.3"},
                {"bk_cloud_id": 3, "conn_ip": "[2001:db8::13]"},
                {"bk_cloud_id": 3, "conn_ip": "127.0.0.3"},
            ],
        )

    def test_empty_items_or_missing_area_returns_empty(self):
        for items in (
            [],
            [host(10, area_id=0, advertise_ip="127.0.0.1")],
            [host(10, area_id=None, advertise_ip="127.0.0.2")],
        ):
            with self.subTest(items=items):
                self.client.list_hosts.return_value = {"total": len(items), "items": items}
                self.assertEqual(get_host_biz_proxies(2), [])

    def test_missing_items_is_treated_as_empty(self):
        self.client.list_hosts.return_value = {}
        self.assertEqual(get_host_biz_proxies(2), [])


@override_settings(ENABLE_NODEMAN_V3=True)
class ProxyHostInfoViewTest(SimpleTestCase):
    def setUp(self):
        self.view = CollectorViewSet()
        self.view.params_valid = Mock(return_value={"space_uid": "bkcc__2"})
        self.toggle = SimpleNamespace(status="on", feature_config={}, biz_id_white_list=[], biz_id_black_list=[])
        patches = {
            "space_api": patch("apps.log_databus.views.collector_views.SpaceApi"),
            "report_toggle": patch("apps.log_databus.views.collector_views.FeatureToggleObject.toggle"),
            "v3_toggle": patch("apps.log_databus.nodeman_v3.mode.get_nodeman_v3_toggle", return_value=self.toggle),
            "v2": patch("apps.log_databus.views.collector_views.NodeApi.get_host_biz_proxies"),
            "v3": patch("apps.log_databus.views.collector_views.get_host_biz_proxies"),
        }
        for name, patcher in patches.items():
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        self.space_api.get_related_space.return_value = SimpleNamespace(bk_biz_id=2)
        self.report_toggle.return_value = SimpleNamespace(
            feature_config={"otlp": {"0": ["grpc:http://default.example:4317"]}}
        )
        self.v2.return_value = [{"bk_cloud_id": 3, "conn_ip": "127.0.0.1"}]
        self.v3.return_value = [{"bk_cloud_id": 3, "conn_ip": "[2001:db8::20]"}]
        self.default_region = {
            "bk_cloud_id": 0,
            "urls": [{"protocol": "grpc", "report_url": "http://default.example:4317"}],
        }

    def test_v3_keeps_response_contract_and_uses_ipv6_urls(self):
        self.v3.return_value.append({"bk_cloud_id": 0, "conn_ip": "127.0.0.3"})

        self.assertEqual(
            self.view.get_proxy_host_info(None).data,
            [
                self.default_region,
                {
                    "bk_cloud_id": 3,
                    "urls": [
                        {"protocol": "grpc", "report_url": "http://[2001:db8::20]:4317"},
                        {"protocol": "http", "report_url": "http://[2001:db8::20]:4318/v1/logs"},
                    ],
                },
            ],
        )
        self.v3.assert_called_once_with(2)
        self.v2.assert_not_called()

    @override_settings(ENABLE_NODEMAN_V3=False)
    def test_total_switch_off_preserves_v2(self):
        response = self.view.get_proxy_host_info(None).data

        self.assertEqual(response[0], self.default_region)
        self.assertEqual(response[1]["urls"][0]["report_url"], "http://127.0.0.1:4317")
        self.v2.assert_called_once_with({"bk_biz_id": 2})
        self.v3.assert_not_called()
        self.v3_toggle.assert_not_called()

    def test_feature_toggle_off_preserves_v2(self):
        self.toggle.status = "off"

        self.view.get_proxy_host_info(None)

        self.v2.assert_called_once_with({"bk_biz_id": 2})
        self.v3.assert_not_called()

    @patch("apps.log_databus.views.collector_views.space_uid_to_bk_biz_id", return_value=-42)
    def test_non_bkcc_space_admission_uses_original_space_but_queries_related_business(self, original_biz):
        self.view.params_valid.return_value = {"space_uid": "bkci__demo"}
        self.toggle.status = "debug"
        self.toggle.biz_id_white_list = [-42]

        self.view.get_proxy_host_info(None)

        original_biz.assert_called_once_with("bkci__demo")
        self.v3.assert_called_once_with(2)
        self.v2.assert_not_called()

    @patch("apps.log_databus.views.collector_views.space_uid_to_bk_biz_id", return_value=-42)
    def test_related_business_whitelist_does_not_admit_original_space(self, original_biz):
        self.view.params_valid.return_value = {"space_uid": "bkci__demo"}
        self.toggle.status = "debug"
        self.toggle.biz_id_white_list = [2]

        self.view.get_proxy_host_info(None)

        self.v2.assert_called_once_with({"bk_biz_id": 2})
        self.v3.assert_not_called()

    def test_no_related_space_only_returns_default_configuration(self):
        self.space_api.get_related_space.return_value = None

        self.assertEqual(self.view.get_proxy_host_info(None).data, [self.default_region])
        self.v2.assert_not_called()
        self.v3.assert_not_called()
        self.v3_toggle.assert_not_called()

    def test_no_proxy_keeps_default_configuration(self):
        self.v3.return_value = []

        self.assertEqual(self.view.get_proxy_host_info(None).data, [self.default_region])
        self.v2.assert_not_called()

    def test_missing_default_configuration_does_not_add_default_region(self):
        self.report_toggle.return_value = None

        response = self.view.get_proxy_host_info(None).data
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]["bk_cloud_id"], 3)

    def test_v3_failure_does_not_fall_back_to_v2(self):
        self.v3.side_effect = NodeManV3APIError("unavailable")

        with self.assertRaises(NodeManV3APIError):
            self.view.get_proxy_host_info(None)
        self.v2.assert_not_called()
