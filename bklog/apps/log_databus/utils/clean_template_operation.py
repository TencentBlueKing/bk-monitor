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

import functools
import inspect

from django.conf import settings

from apps.log_databus.exceptions import CleanTemplateCollectorOperatingException
from apps.utils.lock import RedisLock


COLLECTOR_OPERATION_LOCK_TTL = getattr(settings, "CLEAN_TEMPLATE_COLLECTOR_OPERATION_LOCK_TTL", 30 * 60)


def acquire_clean_template_collector_operation_lock(collector_config_id: int, raise_exception: bool = True):
    """获取采集项维度的清洗模板操作锁。同步任务可选择在冲突时直接跳过。"""
    lock = RedisLock(
        f"clean_template_collector_operation_{collector_config_id}",
        ttl=COLLECTOR_OPERATION_LOCK_TTL,
    )
    if lock.acquire(_wait=0.1):
        return lock
    if raise_exception:
        raise CleanTemplateCollectorOperatingException(
            CleanTemplateCollectorOperatingException.MESSAGE.format(collector_config_id=collector_config_id)
        )
    return None


def lock_clean_template_collector_operation(func):
    """仅为显式绑定/解绑模板的 ETL 请求加锁，保持普通 ETL 更新行为不变。"""
    signature = inspect.signature(func)

    @functools.wraps(func)
    def wrapped(handler, *args, **kwargs):
        bound_arguments = signature.bind(handler, *args, **kwargs).arguments
        collector_config_id = handler.collector_config_id
        is_template_operation = "clean_template_id" in bound_arguments
        lock_managed_by_sync = bound_arguments.get("sync_modify_result_table", False)
        if not collector_config_id or not is_template_operation or lock_managed_by_sync:
            return func(handler, *args, **kwargs)

        lock = acquire_clean_template_collector_operation_lock(collector_config_id)
        try:
            return func(handler, *args, **kwargs)
        finally:
            lock.release()

    return wrapped
