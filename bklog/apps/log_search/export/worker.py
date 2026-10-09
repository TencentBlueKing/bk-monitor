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

import copy
import gzip
import hashlib
import shutil
import tempfile
import time
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings

from apps.api.exception import DataAPIException
from apps.log_search.constants import (
    ASYNC_EXPORT_SCROLL,
    ExportErrorCode,
    ExportPartStatus,
    ExportStage,
)
from apps.log_search.export import state
from apps.log_search.export.config import policy_from_snapshot
from apps.log_search.export.planner import build_handler, encode_export_row
from apps.log_search.export.storage import (
    UnsupportedExportStorage,
    artifact_name,
    build_storage,
)
from apps.utils.log import logger


class PartError(Exception):
    """分片执行的可重试失败，code 会写入分片记录用于排查。"""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code = code


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_rows(handler, payload):
    """
    把分片区间内的日志流式写成 JSONL。

    沿用旧链路的滚动查询，区别是读到 EOF 为止、不受 max_async_count 截断，并且有明确的时间预算。
    """
    params = copy.deepcopy(handler.base_dict)
    params.update(
        {
            "limit": handler.export_result_window,
            "scroll": ASYNC_EXPORT_SCROLL,
            "slice_max": 0,
            "highlight": {"enable": False},
        }
    )
    deadline = time.monotonic() + settings.ASYNC_EXPORT_PART_FETCH_TIMEOUT
    rows = size = 0
    with payload.open("wb") as stream:
        while True:
            if time.monotonic() >= deadline:
                raise PartError(ExportErrorCode.FETCH_TIMEOUT, "分片执行超过时间预算")
            # 与旧异步导出链路一致：首轮清空缓存，后续滚动复用同一份查询上下文
            params["clear_cache"] = rows == 0
            batch, done = handler.export_scroll_batch(params)
            if not batch:
                break
            for row in batch:
                data = encode_export_row(row)
                stream.write(data)
                size += len(data)
            rows += len(batch)
            if done:
                break
    return rows, size


def _pack(directory, part):
    """每个分片独立压缩成裸 jsonl.gz：gzip 多 member 可拼接，便于服务端按序流式合并。"""
    archive = directory / f"part-{part.part_no}.jsonl.gz"
    with (directory / "logs.jsonl").open("rb") as source, gzip.open(archive, "wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)
    return archive


def _upload_with_retry(storage, path, name, part, policy):
    """
    上传失败只在当前进程内重试上传本身：本地压缩文件仍然可用，不会重新查询和压缩。

    重试耗尽后按 UPLOAD_FAILED 上抛，上传失败与工作量无关，不做时间细分。
    """
    attempts = policy.upload_attempts
    interval = policy.upload_retry_interval_seconds
    for attempt in range(1, attempts + 1):
        try:
            return storage.export_upload(file_path=str(path), file_name=name)
        except SoftTimeLimitExceeded:
            raise
        except Exception as error:  # pylint: disable=broad-except
            if attempt >= attempts:
                raise PartError(ExportErrorCode.UPLOAD_FAILED, f"上传重试 {attempts} 次仍失败：{error}") from error
            logger.warning(
                "[run_part] part=%s upload attempt %s/%s failed, retry with local artifact: %s",
                part.pk,
                attempt,
                attempts,
                error,
            )
            time.sleep(interval * attempt)


def _discard_artifact(storage, name, part):
    """本次执行没有被接受时清掉自己写的对象。"""
    try:
        storage.delete_file(name)
    except Exception as error:  # pylint: disable=broad-except
        logger.warning("[run_part] part=%s discard artifact %s failed: %s", part.pk, name, error)


def _execute(job, part, fence):
    storage = build_storage(external=job.is_external)
    policy = policy_from_snapshot(job.policy)
    with tempfile.TemporaryDirectory(prefix=f"bklog-export-{job.pk}-") as directory:
        directory = Path(directory)
        handler = build_handler(job, part.start_time, part.end_time)
        rows, size = _write_rows(handler, directory / "logs.jsonl")
        if not state.set_stage(part.pk, fence, ExportStage.PACKAGE):
            return
        archive = _pack(directory, part)
        if not state.set_stage(part.pk, fence, ExportStage.UPLOAD):
            return
        checksum = _sha256(archive)
        name = artifact_name(job, part, fence.attempts)
        _upload_with_retry(storage, archive, name, part, policy)
        accepted = False
        try:
            result = state.complete_part(
                part.pk,
                fence,
                actual_rows=rows,
                actual_bytes=size,
                compressed_bytes=archive.stat().st_size,
                object_key=name,
                checksum=checksum,
            )
            accepted = result is not None and result.status == ExportPartStatus.SUCCESS
        finally:
            # 只有被接受的执行才留下产物
            if not accepted:
                _discard_artifact(storage, name, part)


def run_part(part_id, task_id):
    """执行一个分片；重复投递、已取消或已回收的投递不会发起任何查询。"""
    part = state.claim_part(part_id, task_id)
    if part is None:
        return
    fence = state.PartFence.of(part)
    try:
        _execute(part.job, part, fence)
    except UnsupportedExportStorage as error:
        # 存储配置问题重试也不会成功，直接给明确错误码
        logger.error("[run_part] part=%s storage unsupported: %s", part.pk, error)
        state.fail_part(
            part.pk, fence, error_code=ExportErrorCode.STORAGE_UNSUPPORTED, error_detail=str(error), retryable=False
        )
    except SoftTimeLimitExceeded:
        # 软超时早于回收窗口，本次执行仍持有栅栏，可以自己把分片交回调度器
        logger.warning("[run_part] part=%s soft time limit exceeded", part.pk)
        state.fail_part(
            part.pk,
            fence,
            error_code=ExportErrorCode.SOFT_TIME_LIMIT_EXCEEDED,
            error_detail="分片执行超过软超时",
            retryable=True,
        )
    except PartError as error:
        logger.warning("[run_part] part=%s code=%s detail=%s", part.pk, error.code, error)
        state.fail_part(part.pk, fence, error_code=error.code, error_detail=str(error), retryable=True)
    except DataAPIException as error:
        # 取数失败可能只是 UnifyQuery 抖动，按可重试处理；与数据密度无关，不做时间细分
        logger.warning("[run_part] part=%s unify query failed: %s", part.pk, error)
        state.fail_part(
            part.pk, fence, error_code=ExportErrorCode.UNIFY_QUERY_FAILED, error_detail=str(error), retryable=True
        )
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("[run_part] part=%s unexpected failure: %s", part.pk, error)
        state.fail_part(
            part.pk,
            fence,
            error_code=ExportErrorCode.PART_EXECUTION_FAILED,
            error_detail=type(error).__name__,
            retryable=True,
        )
