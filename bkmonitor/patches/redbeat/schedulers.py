# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
__implements__ = ["RedBeatSchedulerEntry"]

from celery.app import app_or_default
from celery.utils.log import get_logger
from redbeat import schedulers
from redbeat.schedulers import RedBeatJSONEncoder, RedBeatScheduler
from redbeat.schedulers import RedBeatSchedulerEntry as _RedBeatSchedulerEntry
from redbeat.schedulers import (
    RetryingConnection,
    ScheduleEntry,
    ensure_conf,
    get_redis,
    json,
)
from redis.client import StrictRedis


class RedBeatSchedulerEntry(_RedBeatSchedulerEntry):
    def __init__(self, name=None, task=None, schedule=None, args=None, kwargs=None, enabled=True, **clsargs):
        ScheduleEntry.__init__(self, name=name, task=task, schedule=schedule, args=args, kwargs=kwargs, **clsargs)
        self.enabled = enabled
        ensure_conf(self.app)

    @classmethod
    def from_key(cls, key, app=None):
        ensure_conf(app)
        client = get_redis(app)
        # 解决对接云redis时，pipeline未能取回数据的问题
        definition = client.hget(key, "definition")
        meta = client.hget(key, "meta")

        if not definition:
            raise KeyError(key)

        definition = cls.decode_definition(definition)
        meta = cls.decode_meta(meta)
        definition.update(meta)

        entry = cls(app=app, **definition)
        # celery.ScheduleEntry sets last_run_at = utcnow(), which is confusing and wrong
        entry.last_run_at = meta["last_run_at"]

        return entry

    def _next_instance(self, last_run_at=None, only_update_last_run_at=False):
        entry = ScheduleEntry._next_instance(self, last_run_at=last_run_at)

        if only_update_last_run_at:
            # rollback the update to total_run_count
            entry.total_run_count = self.total_run_count

        meta = {
            "last_run_at": entry.last_run_at,
            "total_run_count": entry.total_run_count,
        }

        with get_redis(self.app).pipeline() as pipe:
            pipe.hset(self.key, "meta", json.dumps(meta, cls=RedBeatJSONEncoder))
            pipe.zadd(self.app.redbeat_conf.schedule_key, {entry.key: entry.score})
            pipe.execute()

        return entry

    __next__ = next = _next_instance


def sentinel_kwargs_get_redis(app=None):
    app = app_or_default(app)
    conf = ensure_conf(app)
    if not hasattr(app, "redbeat_redis") or app.redbeat_redis is None:
        redis_options = conf.app.conf.get("REDBEAT_REDIS_OPTIONS", conf.app.conf.get("BROKER_TRANSPORT_OPTIONS", {}))
        retry_period = redis_options.get("retry_period")
        if conf.redis_url.startswith("redis-sentinel") and "sentinels" in redis_options:
            from redis.sentinel import Sentinel

            sentinel = Sentinel(
                redis_options["sentinels"],
                socket_timeout=redis_options.get("socket_timeout"),
                password=redis_options.get("password"),
                decode_responses=True,
                sentinel_kwargs=redis_options.get("sentinel_kwargs", None),
            )
            connection = sentinel.master_for(redis_options.get("service_name", "master"))
        else:
            connection = StrictRedis.from_url(conf.redis_url, decode_responses=True)

        if retry_period is None:
            app.redbeat_redis = connection
        else:
            app.redbeat_redis = RetryingConnection(retry_period, connection)

    return app.redbeat_redis


RedBeatScheduler.Entry = RedBeatSchedulerEntry
schedulers.get_redis = sentinel_kwargs_get_redis
schedulers.logger = get_logger("celery.beat")
