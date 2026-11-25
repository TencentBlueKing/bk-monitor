"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import runpy
from functools import partial

import pytest
from celery import Celery
from celery.beat import Scheduler

from alarm_backends.service.scheduler import app as scheduler
from alarm_backends.service.scheduler.tasks import cron
from apm.task import TOPO_DISCOVER_TASK_NAME, tasks


@pytest.mark.parametrize("dispatch_queue", ["", "celery_apm_dispatch"])
def test_beat_routes_only_topology_dispatch_to_configured_queue(settings, monkeypatch, dispatch_queue):
    settings.APM_TOPO_DISCOVERY_DISPATCH_QUEUE = dispatch_queue
    with Celery("routing_test", broker="memory://", set_as_current=False) as app:
        # Register the same periodic tasks without changing the process-wide worker registry.
        monkeypatch.setattr(scheduler, "app", app)
        monkeypatch.setattr(app, "task", partial(app.task, shared=False, lazy=False))
        registered = runpy.run_path(cron.__file__, run_name=cron.__name__)
        cron.before_task_publish.disconnect(registered["stamp_discovery_schedule"], sender=TOPO_DISCOVER_TASK_NAME)
        app.finalize()
        beat = Scheduler(app=app, lazy=True)
        entry = beat.Entry(name=TOPO_DISCOVER_TASK_NAME, app=app, **app.conf.beat_schedule[TOPO_DISCOVER_TASK_NAME])
        with app.connection_for_write() as connection:
            result = beat.apply_async(entry, producer=app.amqp.Producer(connection), advance=False)
            expected_queue = dispatch_queue or "celery_cron"
            with connection.SimpleQueue(expected_queue) as queue:
                message = queue.get(block=False)
                assert message.headers["id"] == result.id
                assert message.headers["task"] == TOPO_DISCOVER_TASK_NAME
                assert "discovery_scheduled_at" in message.headers
                message.ack()
        assert app.tasks[cron.apm_task_tasks_datasource_discover_cron.name].queue == "celery_cron"
        assert tasks.handler.queue == "celery_cron"
