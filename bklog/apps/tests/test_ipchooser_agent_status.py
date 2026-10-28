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
