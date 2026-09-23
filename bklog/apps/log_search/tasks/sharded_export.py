"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

"""分片异步导出任务；旧 async_export 队列与入口保持不变。

开关只决定新请求是否进入分片链路，已经准入的任务必须继续收尾，因此任务本身不做开关判断。
"""

from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery.celery import app
from django.conf import settings

from apps.log_search.export.config import CONTROL_QUEUE, PART_QUEUE
from apps.log_search.export.worker import run_part
from apps.log_search.export.planner import run_planning
from apps.log_search.export.scheduler import coordinate, finalize_export
from apps.utils.lock import share_lock


@app.task(
    bind=True,
    ignore_result=True,
    queue=PART_QUEUE,
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_sharded_export_part(self, part_id):
    """投递身份取自 Celery 消息 id，与 dispatch_part 写入分片的 task_id 同值。"""
    run_part(part_id, self.request.id)


@app.task(ignore_result=True, queue=CONTROL_QUEUE)
def plan_sharded_export(job_id):
    run_planning(job_id)


@app.task(ignore_result=True, queue=CONTROL_QUEUE)
def finalize_sharded_export(job_id):
    finalize_export(job_id)


@periodic_task(
    run_every=settings.ASYNC_EXPORT_COORDINATE_INTERVAL_SECONDS,
    options={"queue": CONTROL_QUEUE},
)
@share_lock(ttl=settings.ASYNC_EXPORT_COORDINATE_LOCK_TIMEOUT)
def coordinate_sharded_exports():
    """补回缺失的规划与收尾消息，按额度投递分片，并回收超时分片。"""
    coordinate()
