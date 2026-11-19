from threading import Event
from unittest.mock import Mock

import pytest
from redis.exceptions import ConnectionError, LockNotOwnedError

from alarm_backends.core.lock import service_lock
from metadata.models.custom_report.subscription_config import CustomReportSubscription
from metadata.task import custom_report


@pytest.fixture
def lock(mocker):
    cache = mocker.patch.object(service_lock, "Cache").return_value
    mocker.patch.object(service_lock, "get_cluster").return_value.name = "default"
    return cache.lock


def test_full_refresh_skips_occupied_legacy_key(lock, mocker):
    lock.return_value.acquire.return_value = False
    refresh = mocker.patch.object(custom_report, "refresh_custom_report_2_node_man")
    custom_report.refresh_all_custom_report_2_node_man()
    lock.assert_called_once_with(
        "default_celery_lock_refresh_custom_report_2_node_man", timeout=600, thread_local=False
    )
    lock.return_value.acquire.assert_called_once_with(blocking=False)
    lock.return_value.release.assert_not_called()
    refresh.assert_not_called()


def test_long_refresh_keeps_renewing_the_same_lock(lock):
    renewed = Event()
    redis_lock = lock.return_value

    def reacquire():
        if redis_lock.reacquire.call_count >= 4:
            renewed.set()

    redis_lock.reacquire.side_effect = reacquire
    with service_lock.renewing_share_lock("refresh", ttl=0.3) as check:
        assert renewed.wait(timeout=3)
        check()
    redis_lock.release.assert_called_once()


@pytest.mark.parametrize("error", [ConnectionError(), LockNotOwnedError()])
def test_renewal_failure_stops_delivery(lock, mocker, error):
    lost = Event()
    mocker.patch.object(service_lock.logger, "exception", side_effect=lambda *args: lost.set())
    lock.return_value.reacquire.side_effect = error
    with pytest.raises(service_lock.CronLeaseLost), service_lock.renewing_share_lock("refresh", ttl=0.3) as check:
        assert lost.wait(timeout=2)
        check()
    lock.return_value.release.assert_called_once()


def test_custom_report_checks_lease_before_next_nodeman_delivery(mocker):
    mocker.patch(
        "metadata.models.custom_report.subscription_config.BkCollectorDeployPolicy.is_enabled", return_value=True
    )
    deploy = mocker.patch("metadata.models.custom_report.subscription_config.BkCollectorDeployPolicy.deploy")
    check = Mock(side_effect=[None, service_lock.CronLeaseLost()])
    with pytest.raises(service_lock.CronLeaseLost):
        CustomReportSubscription.create_subscription(
            bk_tenant_id="system",
            bk_biz_id=1,
            data_id_configs=[({"bk_data_id": 101}, "json"), ({"bk_data_id": 102}, "json")],
            bk_host_ids=[123],
            check_lease=check,
        )
    assert [call.kwargs["context"]["bk_data_id"] for call in deploy.call_args_list] == [101]


def test_lost_lease_is_not_handled_as_a_tenant_delivery_error(mocker):
    mocker.patch.object(custom_report.models.BkCollectorDeployPolicy, "is_enabled", return_value=True)
    mocker.patch.object(custom_report.api.bk_login, "list_tenant", return_value=[{"id": "a"}, {"id": "b"}])
    refresh = mocker.patch.object(
        CustomReportSubscription, "refresh_collector_custom_conf", side_effect=service_lock.CronLeaseLost()
    )
    with pytest.raises(service_lock.CronLeaseLost):
        custom_report.refresh_custom_report_2_node_man(check_lease=Mock())
    assert refresh.call_count == 1
