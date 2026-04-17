from unittest.mock import MagicMock

import pytest

from metadata.task.bkbase import watch_bkbase_meta_redis


pytestmark = pytest.mark.django_db(databases="__all__")


def test_watch_bkbase_meta_redis_exits_when_no_message_within_runtime_limit(mocker):
    pubsub = MagicMock()
    pubsub.get_message.return_value = None

    redis_conn = MagicMock()
    redis_conn.pubsub.return_value = pubsub

    mocker.patch(
        "metadata.task.bkbase.time.monotonic",
        side_effect=[0, 0, 0.4, 0.8, 1.2, 1.2],
    )

    watch_bkbase_meta_redis(redis_conn=redis_conn, key_pattern="databus_v4_dataid:*", runtime_limit=1)

    redis_conn.pubsub.assert_called_once_with()
    pubsub.psubscribe.assert_called_once_with("__keyspace@0__:databus_v4_dataid:*")
    assert pubsub.get_message.call_count == 2
    pubsub.close.assert_called_once_with()


def test_watch_bkbase_meta_redis_dispatches_message(mocker):
    pubsub = MagicMock()
    pubsub.get_message.side_effect = [
        {
            "type": "pmessage",
            "channel": b"__keyspace@0__:databus_v4_dataid:123",
            "data": b"set",
        },
        None,
    ]

    redis_conn = MagicMock()
    redis_conn.pubsub.return_value = pubsub
    mock_delay = mocker.patch("metadata.task.bkbase.sync_bkbase_v4_metadata.delay")
    mocker.patch(
        "metadata.task.bkbase.time.monotonic",
        side_effect=[0, 0, 0.2, 0.4, 1.2, 1.2],
    )

    watch_bkbase_meta_redis(redis_conn=redis_conn, key_pattern="databus_v4_dataid:*", runtime_limit=1)

    mock_delay.assert_called_once_with(key="databus_v4_dataid:123", skip_types=["es"])
    pubsub.close.assert_called_once_with()
