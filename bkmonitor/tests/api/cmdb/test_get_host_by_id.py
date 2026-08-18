from unittest import mock

from api.cmdb import default as cmdb


HOST_FIELDS = ["bk_host_id", "bk_host_innerip", "bk_host_innerip_v6", "bk_cloud_id", "bk_host_name"]


def build_host_record(host_id=1, ipv4="host-ipv4", ipv6="", module_ids=(10, 11)):
    return {
        "host": {
            "bk_host_id": host_id,
            "bk_host_innerip": ipv4,
            "bk_host_innerip_v6": ipv6,
            "bk_cloud_id": 0,
            "bk_host_name": f"host-{host_id}",
        },
        "topo": [
            {
                "bk_set_id": 20,
                "bk_set_name": "set-a",
                "module": [
                    {"bk_module_id": module_id, "bk_module_name": f"module-{module_id}"} for module_id in module_ids
                ],
            }
        ],
    }


def test_get_host_by_id_skips_cmdb_for_empty_ids(mocker):
    list_hosts = mocker.patch.object(cmdb.client, "list_biz_hosts_topo")
    batch_request = mocker.patch.object(cmdb, "batch_request")
    search_cloud_area = mocker.patch.object(cmdb.api.cmdb, "search_cloud_area")

    result = cmdb.GetHostById().perform_request({"bk_biz_id": 2, "bk_host_ids": [], "fields": HOST_FIELDS})

    assert result == []
    list_hosts.assert_not_called()
    batch_request.assert_not_called()
    search_cloud_area.assert_not_called()


def test_get_host_by_id_uses_one_page_for_deduplicated_ids(mocker):
    record = build_host_record(host_id=7, ipv4="", ipv6="host-ipv6")
    list_hosts = mocker.patch.object(
        cmdb.client,
        "list_biz_hosts_topo",
        return_value={"count": 1, "info": [record]},
    )
    batch_request = mocker.patch.object(cmdb, "batch_request")
    mocker.patch.object(cmdb.api.cmdb, "search_cloud_area", return_value=[])

    result = cmdb.GetHostById().perform_request({"bk_biz_id": 2, "bk_host_ids": [7, 7], "fields": HOST_FIELDS})

    list_hosts.assert_called_once_with(
        {
            "bk_biz_id": 2,
            "host_property_filter": {
                "condition": "AND",
                "rules": [{"field": "bk_host_id", "operator": "in", "value": [7]}],
            },
            "fields": HOST_FIELDS,
            "page": {"start": 0, "limit": 500},
        }
    )
    batch_request.assert_not_called()
    assert len(result) == 1
    assert result[0].bk_host_innerip_v6 == "host-ipv6"
    assert result[0].bk_set_ids == [20]
    assert result[0].bk_module_ids == [10, 11]


def test_get_host_by_id_uses_one_page_for_500_unique_ids(mocker):
    list_hosts = mocker.patch.object(
        cmdb.client,
        "list_biz_hosts_topo",
        return_value={"count": 0, "info": []},
    )
    batch_request = mocker.patch.object(cmdb, "batch_request")
    mocker.patch.object(cmdb.api.cmdb, "search_cloud_area", return_value=[])

    cmdb.GetHostById().perform_request({"bk_biz_id": 2, "bk_host_ids": list(range(1, 501)), "fields": HOST_FIELDS})

    assert list_hosts.call_count == 1
    assert list_hosts.call_args.args[0]["page"] == {"start": 0, "limit": 500}
    batch_request.assert_not_called()


def test_get_host_by_id_falls_back_when_single_page_is_incomplete(mocker):
    first_record = build_host_record(host_id=1)
    second_record = build_host_record(host_id=2)
    mocker.patch.object(
        cmdb.client,
        "list_biz_hosts_topo",
        return_value={"count": 2, "info": [first_record]},
    )
    batch_request = mocker.patch.object(cmdb, "batch_request", return_value=[first_record, second_record])
    mocker.patch.object(cmdb.api.cmdb, "search_cloud_area", return_value=[])

    result = cmdb.GetHostById().perform_request({"bk_biz_id": 2, "bk_host_ids": [1, 2], "fields": HOST_FIELDS})

    batch_request.assert_called_once_with(cmdb.client.list_biz_hosts_topo, mock.ANY)
    assert [host.bk_host_id for host in result] == [1, 2]


def test_get_host_by_id_keeps_batch_request_for_more_than_500_ids(mocker):
    list_hosts = mocker.patch.object(cmdb.client, "list_biz_hosts_topo")
    batch_request = mocker.patch.object(cmdb, "batch_request", return_value=[])
    mocker.patch.object(cmdb.api.cmdb, "search_cloud_area", return_value=[])

    cmdb.GetHostById().perform_request({"bk_biz_id": 2, "bk_host_ids": list(range(1, 502)), "fields": HOST_FIELDS})

    list_hosts.assert_not_called()
    batch_request.assert_called_once_with(cmdb.client.list_biz_hosts_topo, mock.ANY)
