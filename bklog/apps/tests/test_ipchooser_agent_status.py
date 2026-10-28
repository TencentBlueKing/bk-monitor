from unittest.mock import patch

from django.test import SimpleTestCase

from bkm_ipchooser.handlers.topo_handler import TopoHandler


class FillAgentStatusTest(SimpleTestCase):
    def setUp(self):
        self.hosts = [
            {"bk_host_id": 1, "bk_host_innerip": "127.0.0.1"},
            {"bk_host_id": 2, "bk_host_innerip": "127.0.0.2"},
            {"bk_host_id": 3, "bk_host_innerip": "127.0.0.3"},
        ]

    @patch("bkm_ipchooser.handlers.topo_handler.TopoHandler._should_use_nodeman_v3", return_value=False)
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

    @patch("bkm_ipchooser.handlers.topo_handler.TopoHandler._should_use_nodeman_v3", return_value=True)
    @patch("apps.log_databus.nodeman_v3.client.get_client")
    def test_v3_path_maps_status_and_missing_hosts(self, mock_get_client, mock_admitted):
        mock_get_client.return_value.list_hosts.return_value = {
            "items": [
                {"bk_host_id": 1, "state": {"node_status": "running"}},
                {"bk_host_id": 2, "state": {"node_status": "starting"}},
            ]
        }

        result = TopoHandler.fill_agent_status(self.hosts, 2)

        self.assertTrue(result[0]["status"])
        self.assertFalse(result[1]["status"])
        # V3 只返回已注册主机，未返回的主机必须视为不在线
        self.assertFalse(result[2]["status"])
        mock_get_client.assert_called_once_with(2)
        call_args = mock_get_client.return_value.list_hosts.call_args[0][0]
        self.assertEqual(call_args["exact_include_conditions"]["bk_biz_id"], [2])
        self.assertEqual(call_args["exact_include_conditions"]["bk_host_id"], [1, 2, 3])

    @patch("bkm_ipchooser.handlers.topo_handler.TopoHandler._should_use_nodeman_v3", return_value=True)
    @patch("apps.log_databus.nodeman_v3.client.get_client")
    def test_v3_failure_keeps_host_list(self, mock_get_client, mock_admitted):
        mock_get_client.return_value.list_hosts.side_effect = RuntimeError("boom")

        result = TopoHandler.fill_agent_status(self.hosts, 2)

        self.assertEqual(len(result), 3)
        self.assertTrue(all(host["status"] is False for host in result))

    @patch("bkm_ipchooser.handlers.topo_handler.TopoHandler._should_use_nodeman_v3", return_value=True)
    @patch("apps.log_databus.nodeman_v3.client.get_client")
    def test_v3_path_paginates_hosts(self, mock_get_client, mock_admitted):
        hosts = [{"bk_host_id": index} for index in range(1, 502)]
        mock_get_client.return_value.list_hosts.return_value = {"items": []}

        TopoHandler.fill_agent_status(hosts, 2)

        self.assertEqual(mock_get_client.return_value.list_hosts.call_count, 2)
