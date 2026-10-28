from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.feature_toggle.handlers.toggle import Toggle
from apps.log_databus.models import CollectorConfig
from apps.log_databus.nodeman_v3.mode import should_use_nodeman_v3
from apps.log_search.constants import AgentStatusEnum
from apps.log_search.handlers.biz import BizHandler
from bkm_ipchooser.handlers.topo_handler import TopoHandler


class FillAgentStatusTest(SimpleTestCase):
    def setUp(self):
        self.hosts = [
            {"bk_host_id": 1, "bk_host_innerip": "127.0.0.1"},
            {"bk_host_id": 2, "bk_host_innerip": "127.0.0.2"},
            {"bk_host_id": 3, "bk_host_innerip": "127.0.0.3"},
        ]

    @patch("bkm_ipchooser.handlers.topo_handler.is_nodeman_v3_admitted", return_value=False)
    @patch("bkm_ipchooser.handlers.topo_handler.BaseHandler.get_meta_data", return_value={})
    @patch("bkm_ipchooser.handlers.topo_handler.BKNodeApi.ipchooser_host_details")
    def test_v2_path(self, mock_details, mock_meta, mock_admitted):
        mock_details.return_value = [{"host_id": 1, "alive": True}, {"host_id": 2, "alive": False}]

        result = TopoHandler.fill_agent_status(self.hosts, 2)

        self.assertTrue(result[0]["status"])
        self.assertFalse(result[1]["status"])
        # V2 只覆盖返回值中的主机，未返回的主机保持原状
        self.assertNotIn("status", result[2])
        mock_details.assert_called_once()

    @patch("bkm_ipchooser.handlers.topo_handler.is_nodeman_v3_admitted", return_value=True)
    @patch("bkm_ipchooser.handlers.topo_handler.get_agent_status")
    def test_v3_path_maps_status_and_missing_hosts(self, mock_get_agent_status, mock_admitted):
        mock_get_agent_status.return_value = {1: True, 2: False}

        result = TopoHandler.fill_agent_status(self.hosts, 2)

        self.assertTrue(result[0]["status"])
        self.assertFalse(result[1]["status"])
        # 公共查询未返回的主机在 IP 选择器侧仍为不在线
        self.assertFalse(result[2]["status"])
        mock_get_agent_status.assert_called_once_with(2, [1, 2, 3])

    @patch("bkm_ipchooser.handlers.topo_handler.is_nodeman_v3_admitted", return_value=True)
    @patch("bkm_ipchooser.handlers.topo_handler.get_agent_status")
    def test_v3_failure_keeps_host_list(self, mock_get_agent_status, mock_admitted):
        mock_get_agent_status.side_effect = RuntimeError("boom")

        result = TopoHandler.fill_agent_status(self.hosts, 2)

        self.assertEqual(len(result), 3)
        self.assertTrue(all(host["status"] is False for host in result))

    @patch("bkm_ipchooser.handlers.topo_handler.is_nodeman_v3_admitted", return_value=True)
    @patch("apps.log_databus.nodeman_v3.agent_status.get_client")
    def test_v3_path_normalizes_numeric_string_host_ids(self, mock_get_client, mock_admitted):
        mock_get_client.return_value.list_hosts.return_value = {
            "items": [
                {"bk_host_id": "1", "state": {"node_status": "running"}},
                {"bk_host_id": "2", "state": {"node_status": "starting"}},
            ]
        }

        result = TopoHandler.fill_agent_status(self.hosts, 2)

        self.assertTrue(result[0]["status"])
        self.assertFalse(result[1]["status"])
        self.assertFalse(result[2]["status"])

    @patch("bkm_ipchooser.handlers.topo_handler.is_nodeman_v3_admitted", return_value=True)
    @patch("apps.log_databus.nodeman_v3.agent_status.get_client")
    def test_v3_path_skips_invalid_and_unrequested_host_ids(self, mock_get_client, mock_admitted):
        mock_get_client.return_value.list_hosts.return_value = {
            "items": [
                {"bk_host_id": None},
                {"bk_host_id": "invalid"},
                {},
                {"bk_host_id": 2, "state": {"node_status": "running"}},
                {"bk_host_id": "99", "state": {"node_status": "running"}},
            ]
        }

        result = TopoHandler.fill_agent_status(self.hosts, 2)

        self.assertFalse(result[0]["status"])
        self.assertTrue(result[1]["status"])
        self.assertFalse(result[2]["status"])

    @override_settings(ENABLE_NODEMAN_V3=True)
    def test_non_bkcc_space_admission_matches_collector_and_query_uses_related_biz(self):
        toggle = Toggle(status="debug", biz_id_white_list=[-99])
        config = CollectorConfig(collector_config_id=9001, bk_biz_id=-99, subscription_id=None)
        with (
            patch("apps.log_databus.nodeman_v3.mode.get_nodeman_v3_toggle", return_value=toggle),
            patch("apps.log_databus.nodeman_v3.models.NodeManV3Binding.objects.filter") as bindings,
            patch("bkm_ipchooser.handlers.topo_handler.get_non_bkcc_space_related_bkcc_biz_id", return_value=2),
            patch("apps.log_databus.nodeman_v3.agent_status.get_client") as mock_get_client,
            patch("bkm_ipchooser.handlers.topo_handler.BaseHandler.get_meta_data", return_value={}),
            patch("bkm_ipchooser.handlers.topo_handler.BKNodeApi.ipchooser_host_details", return_value=[]) as v2_query,
        ):
            bindings.return_value.values_list.return_value = []
            mock_get_client.return_value.list_hosts.return_value = {
                "items": [{"bk_host_id": 1, "state": {"node_status": "running"}}]
            }

            self.assertTrue(should_use_nodeman_v3(config))
            result = TopoHandler.fill_agent_status(self.hosts, -99)

        self.assertTrue(result[0].get("status"))
        self.assertFalse(result[1].get("status"))
        self.assertFalse(result[2].get("status"))
        mock_get_client.assert_called_once_with(2)
        payload = mock_get_client.return_value.list_hosts.call_args.args[0]
        self.assertEqual(payload["exact_include_conditions"]["bk_biz_id"], [2])
        self.assertEqual(payload["exact_include_conditions"]["bk_host_id"], [1, 2, 3])
        v2_query.assert_not_called()

    @override_settings(ENABLE_NODEMAN_V3=True)
    def test_non_bkcc_space_keeps_v2_when_only_related_biz_is_whitelisted(self):
        toggle = Toggle(status="debug", biz_id_white_list=[2])
        config = CollectorConfig(collector_config_id=9001, bk_biz_id=-99, subscription_id=None)
        meta = {"scope_type": "biz", "scope_id": "-99", "bk_biz_id": -99}
        with (
            patch("apps.log_databus.nodeman_v3.mode.get_nodeman_v3_toggle", return_value=toggle),
            patch("apps.log_databus.nodeman_v3.models.NodeManV3Binding.objects.filter") as bindings,
            patch("bkm_ipchooser.handlers.topo_handler.get_non_bkcc_space_related_bkcc_biz_id", return_value=2),
            patch("bkm_ipchooser.handlers.topo_handler.get_agent_status") as v3_query,
            patch("bkm_ipchooser.handlers.topo_handler.BaseHandler.get_meta_data", return_value=meta) as mock_meta,
            patch("bkm_ipchooser.handlers.topo_handler.BKNodeApi.ipchooser_host_details") as v2_query,
        ):
            bindings.return_value.values_list.return_value = []
            v2_query.return_value = [{"host_id": 1, "alive": True}]

            self.assertFalse(should_use_nodeman_v3(config))
            result = TopoHandler.fill_agent_status(self.hosts, -99)

        self.assertTrue(result[0]["status"])
        mock_meta.assert_called_once_with(-99)
        request_params = v2_query.call_args.args[0]
        self.assertEqual(request_params["scope_list"], [{"scope_type": "biz", "scope_id": "-99"}])
        self.assertEqual(request_params["host_list"][0]["meta"], meta)
        v3_query.assert_not_called()


class BizAgentStatusTest(SimpleTestCase):
    @override_settings(ENABLE_NODEMAN_V3=True)
    def test_non_bkcc_space_uses_original_biz_for_admission_and_related_biz_for_query(self):
        toggle = Toggle(status="debug", biz_id_white_list=[-99])
        with (
            patch("apps.log_databus.nodeman_v3.mode.get_nodeman_v3_toggle", return_value=toggle),
            patch("apps.log_search.handlers.biz.get_non_bkcc_space_related_bkcc_biz_id", return_value=2),
            patch("apps.log_search.handlers.biz.BaseHandler.get_meta_data", return_value={}) as mock_meta,
            patch("apps.log_databus.nodeman_v3.agent_status.get_client") as mock_get_client,
            patch("apps.log_search.handlers.biz.NodeApi.ipchooser_host_details", return_value=[]) as v2_query,
        ):
            mock_get_client.return_value.list_hosts.return_value = {
                "items": [{"bk_host_id": 1, "state": {"node_status": "running"}}]
            }

            handler = BizHandler(-99)
            result = handler.get_agent_status([{"bk_host_id": 1}])

        self.assertEqual(handler.bk_biz_id, 2)
        self.assertEqual(result[1], AgentStatusEnum.ON.value)
        mock_meta.assert_called_once_with(2)
        mock_get_client.assert_called_once_with(2)
        v2_query.assert_not_called()

    @override_settings(ENABLE_NODEMAN_V3=True)
    def test_non_bkcc_space_keeps_v2_when_only_related_biz_is_whitelisted(self):
        toggle = Toggle(status="debug", biz_id_white_list=[2])
        with (
            patch("apps.log_databus.nodeman_v3.mode.get_nodeman_v3_toggle", return_value=toggle),
            patch("apps.log_search.handlers.biz.get_non_bkcc_space_related_bkcc_biz_id", return_value=2),
            patch("apps.log_search.handlers.biz.BaseHandler.get_meta_data", return_value={}),
            patch("apps.log_search.handlers.biz.get_agent_status", return_value={1: True}) as v3_query,
            patch("apps.log_search.handlers.biz.NodeApi.ipchooser_host_details") as v2_query,
        ):
            v2_query.return_value = [{"host_id": 1, "alive": True}]

            handler = BizHandler(-99)
            result = handler.get_agent_status([{"bk_host_id": 1}])

        self.assertEqual(handler.bk_biz_id, 2)
        self.assertEqual(result[1], AgentStatusEnum.ON.value)
        v2_query.assert_called_once()
        request_params = v2_query.call_args.args[0]
        self.assertEqual(request_params["scope_list"], [{"scope_type": "biz", "scope_id": "2"}])
        v3_query.assert_not_called()
