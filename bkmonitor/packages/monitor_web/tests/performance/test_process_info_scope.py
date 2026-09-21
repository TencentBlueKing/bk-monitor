from types import SimpleNamespace

import pytest

from monitor_web.cc.resources import cmdb


@pytest.mark.parametrize(
    "host_ids,push_target,expected",
    [
        ([2, 3], True, {"bk_biz_id": 2, "bk_host_id": None, "bk_host_ids": [2, 3]}),
        ([2, 3], False, {"bk_biz_id": 2, "bk_host_id": None}),
        ([2], True, {"bk_biz_id": 2, "bk_host_id": 2}),
        ([2], False, {"bk_biz_id": 2, "bk_host_id": 2}),
    ],
)
def test_process_info_pushes_page_host_ids_without_changing_single_host_or_full_mode(
    mocker, host_ids, push_target, expected
):
    get_process = mocker.patch.object(cmdb.api.cmdb, "get_process", return_value=[])
    get_status = mocker.patch.object(cmdb, "get_process_status", return_value={})
    hosts = [SimpleNamespace(bk_host_id=host_id) for host_id in host_ids]
    assert cmdb.get_process_info(2, hosts, push_host_target=push_target) == {}
    get_process.assert_called_once_with(**expected)
    assert get_status.call_args.kwargs["push_host_target"] is push_target
