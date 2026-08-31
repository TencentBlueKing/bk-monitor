from unittest.mock import MagicMock

from alarm_backends.core.lock import RedisLock


def test_redis_lock_refreshes_only_its_own_token():
    lock = object.__new__(RedisLock)
    lock.name = "lock-key"
    lock.ttl = 60
    lock.client = MagicMock()
    lock._RedisLock__token = "lock-token"
    lock.client.eval.return_value = 1

    assert lock.refresh() is True
    lock.client.eval.assert_called_once_with(
        lock.REFRESH_SCRIPT,
        1,
        "lock-key",
        "lock-token",
        60,
    )
