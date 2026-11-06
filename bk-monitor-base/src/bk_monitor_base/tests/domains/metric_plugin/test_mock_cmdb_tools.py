import pytest

from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.mock_cmdb_tools import get_host_info, get_os_type_by_collect_host


@pytest.mark.parametrize(
    ("bk_cpu_architecture", "expected_arch", "expected_os_type"),
    [
        ("x86", "x86_64", OSType.LINUX),
        ("arm", "aarch64", OSType.LINUX_AARCH64),
    ],
)
def test_get_host_info_normalizes_cmdb_cpu_architecture(
    mocker,
    bk_cpu_architecture: str,
    expected_arch: str,
    expected_os_type: OSType,
):
    mocker.patch(
        "bk_monitor_base.domains.metric_plugin.mock_cmdb_tools.search_instances",
        return_value=(
            1,
            [
                {
                    "bk_host_id": 1,
                    "bk_host_innerip": "127.0.0.1",
                    "bk_os_type": "1",
                    "bk_cpu_architecture": bk_cpu_architecture,
                }
            ],
        ),
    )

    host_info = get_host_info({"bk_host_id": 1})

    assert host_info is not None
    assert host_info["os_arch"] == expected_arch
    assert get_os_type_by_collect_host({"bk_host_id": 1}) == expected_os_type
