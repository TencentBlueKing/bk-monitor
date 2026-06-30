from api.cmdb.define import Host
from metadata.task.ping_server import refresh_ping_conf


def make_host(bk_biz_id: int, bk_host_id: int, bk_cloud_id: int, ip: str) -> Host:
    return Host(
        {
            "bk_biz_id": bk_biz_id,
            "bk_host_id": bk_host_id,
            "bk_cloud_id": bk_cloud_id,
            "bk_host_innerip": ip,
        }
    )


def test_refresh_ping_conf_filters_new_env_biz_black_list(settings, mocker):
    settings.ENABLE_PING_ALARM = True
    settings.NEW_ENV_BIZ_BLACK_LIST = [2, 0]

    mocker.patch("metadata.task.ping_server.api.bk_login.list_tenant", return_value=[{"id": "system"}])
    mocker.patch(
        "alarm_backends.core.cache.cmdb.host.HostManager.all",
        return_value=[
            make_host(bk_biz_id=0, bk_host_id=4, bk_cloud_id=100, ip="127.0.0.1"),
            make_host(bk_biz_id=2, bk_host_id=1, bk_cloud_id=100, ip="127.0.0.1"),
            make_host(bk_biz_id=3, bk_host_id=2, bk_cloud_id=100, ip="127.0.0.2"),
            make_host(bk_biz_id=2, bk_host_id=3, bk_cloud_id=101, ip="127.0.0.3"),
        ],
    )
    refresh_by_cloud_id = mocker.patch("metadata.task.ping_server._refresh_ping_conf_by_cloud_id")

    refresh_ping_conf("bk-collector")

    refresh_by_cloud_id.assert_called_once_with(
        "system",
        100,
        "bk-collector",
        [
            {"ip": "127.0.0.1", "bk_cloud_id": 100, "bk_biz_id": 0, "bk_host_id": 4},
            {"ip": "127.0.0.2", "bk_cloud_id": 100, "bk_biz_id": 3, "bk_host_id": 2},
        ],
    )
