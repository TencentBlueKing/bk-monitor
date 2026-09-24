"""验证 Base 迁入后的 IP 例外仅覆盖已核实的文件和值。"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class BaseAllowlistTests(unittest.TestCase):
    """使用真实检查脚本，确保例外没有放行新增地址或其他文件。"""

    def check_address(self, relative_path: str, content: str) -> int:
        """在临时工作目录运行主仓 IP 检查，不修改真实夹具。"""
        script = Path(__file__).resolve().parents[1] / "ip.sh"
        env = {key: value for key, value in os.environ.items() if key != "BK_IP_WHITELIST_FILES"}
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / relative_path
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text(content)
            result = subprocess.run(
                [str(script), relative_path], cwd=directory, env=env, capture_output=True, check=False
            )
        return result.returncode

    def test_known_fixture_value_only(self):
        """同一夹具的既有示例通过，新增地址仍被拦截。"""
        path = "bk-monitor-base/src/bk_monitor_base/tests/domains/cmdb_instance/test_operations.py"
        self.assertEqual(self.check_address(path, 'ip = "10.0.0.1"'), 0)
        self.assertEqual(self.check_address(path, 'ip = "192.0.2.254"'), 1)

    def test_other_fixture_not_exempt(self):
        """其他测试文件没有因同目录被放行。"""
        path = "bk-monitor-base/src/bk_monitor_base/tests/domains/cmdb_instance/test_new.py"
        self.assertEqual(self.check_address(path, 'ip = "10.0.0.1"'), 1)

    def test_oid_does_not_exempt_address(self):
        """OID 片段例外不影响文档中新地址的检查。"""
        path = "bk-monitor-base/src/bk_monitor_base/domains/metric_plugin/docs/snmp_plugin_doc.md"
        self.assertEqual(self.check_address(path, "oid: 1.3.6.1.2.1.1.3.0"), 0)
        self.assertEqual(self.check_address(path, "host: 192.0.2.254"), 1)

    def test_lockfile_version_only(self):
        """锁文件只放行核实过的版本号，不整体排除。"""
        path = "bk-monitor-base/uv.lock"
        self.assertEqual(self.check_address(path, 'version = "1.1.1.2"'), 0)
        self.assertEqual(self.check_address(path, 'url = "http://192.0.2.254"'), 1)

    def test_binary_new_address_not_exempt(self):
        """现有二进制的精确例外仍会拦截新增 IP。"""
        path = (
            "bk-monitor-base/src/bk_monitor_base/domains/metric_plugin/manager/node_man/"
            "templates/snmp/external_plugins_linux_x86_64/plugin_name/snmp_exporter"
        )
        self.assertEqual(self.check_address(path, "\x00new address 192.0.2.254\x00"), 1)


if __name__ == "__main__":
    unittest.main()
