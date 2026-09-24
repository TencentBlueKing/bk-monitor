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
import hashlib
import tarfile
import tempfile
import time
from pathlib import Path

from django.conf import settings

from apps.api import UnifyQueryApi
from apps.api.exception import DataAPIException
from apps.log_search.constants import ASYNC_EXPORT_SCROLL, MAX_RESULT_WINDOW, ExportErrorCode, ExportStage
from apps.log_search.export import state
from apps.log_search.export.planner import build_handler, encode_export_row
from apps.log_search.export.storage import UnsupportedExportStorage, artifact_name, build_storage, upload
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

    沿用旧异步导出链路的滚动查询方式（query_ts_raw_with_scroll + _deal_query_result），
    区别是显式读到 EOF 为止、不受 max_async_count 截断，并且有明确的时间预算。
    """
    index_set = handler.index_info_list[0]["index_set_obj"]
    params = copy.deepcopy(handler.base_dict)
    params.update(
        {
            "limit": index_set.result_window or MAX_RESULT_WINDOW,
            "scroll": ASYNC_EXPORT_SCROLL,
            "slice_max": 0,
            "highlight": {"enable": False},
        }
    )
    deadline = time.monotonic() + settings.ASYNC_EXPORT_PART_TIMEOUT
    rows = size = 0
    with payload.open("wb") as stream:
        while True:
            if time.monotonic() >= deadline:
                raise PartError(ExportErrorCode.PART_TIMEOUT, "分片执行超过时间预算")
            # 与旧异步导出链路一致：首轮清空缓存，后续滚动复用同一份查询上下文
            params["clear_cache"] = rows == 0
            result = UnifyQueryApi.query_ts_raw_with_scroll(params)
            batch = result["list"]
            if not batch:
                break
            for row in handler._deal_query_result(result)["origin_log_list"]:
                data = encode_export_row(row)
                stream.write(data)
                size += len(data)
            rows += len(batch)
            if result.get("done"):
                break
    return rows, size


def _pack(directory, part):
    """每个分片独立压缩，避免 Worker 内合并大文件。"""
    archive = directory / f"part-{part.part_no}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(directory / "logs.jsonl", arcname="logs.log")
    return archive


def _upload_with_retry(storage, path, name, part):
    """
    上传失败只在当前进程内重试上传本身。

    本地压缩文件在分片执行期间一直可用，重试不会重新查询和重新压缩（取数与转换约占
    单分片成本的 80%）。重试耗尽后按 UPLOAD_FAILED 上抛：上传失败与分片工作量无关，
    只让当前分片回到 WAITING，重试次数用尽后整片失败，不做时间细分。
    """
    attempts = settings.ASYNC_EXPORT_UPLOAD_ATTEMPTS
    interval = settings.ASYNC_EXPORT_UPLOAD_RETRY_INTERVAL_SECONDS
    for attempt in range(1, attempts + 1):
        try:
            return upload(storage, path, name)
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


def _execute(job, part, fence):
    storage = build_storage(external=job.is_external)
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
        name = artifact_name(job, part.part_no)
        _upload_with_retry(storage, archive, name, part)
        state.complete_part(
            part.pk,
            fence,
            actual_rows=rows,
            actual_bytes=size,
            compressed_bytes=archive.stat().st_size,
            object_key=name,
            checksum=checksum,
        )


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
    except PartError as error:
        logger.warning("[run_part] part=%s code=%s detail=%s", part.pk, error.code, error)
        state.fail_part(part.pk, fence, error_code=error.code, error_detail=str(error), retryable=True)
    except DataAPIException as error:
        # 取数失败可能只是 UnifyQuery 抖动或查询过重，按可重试处理，重试耗尽仍允许按时间细分
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
