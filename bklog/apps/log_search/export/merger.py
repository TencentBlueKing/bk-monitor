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

import hashlib
import tempfile
from pathlib import Path

from apps.log_search.export.storage import build_storage, merged_name


class _DigestWriter:
    """把写入同时喂给 sha256 并累计字节数，避免合并后再整文件重读一遍算校验值。"""

    def __init__(self, raw, digest):
        self._raw = raw
        self._digest = digest
        self.size = 0

    def write(self, chunk):
        self._digest.update(chunk)
        self.size += len(chunk)
        return self._raw.write(chunk)


def merge_export_parts(job, parts):
    """
    把已成功分片按传入顺序（调用方按 start_time, part_no 排序）字节拼接成单个 jsonl.gz 并上传。

    分片产物是裸 gzip，gzip 支持多 member 拼接：合并即按序字节拷贝，不需要解压或重压缩，
    内存占用与单次读块同阶。返回 (object_key, bytes, checksum)。
    """
    storage = build_storage(external=job.is_external)
    name = merged_name(job)
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix=f"bklog-export-merge-{job.pk}-") as directory:
        path = Path(directory) / "full.jsonl.gz"
        with path.open("wb") as raw:
            writer = _DigestWriter(raw, digest)
            for part in parts:
                storage.download_fileobj(part.object_key, writer)
        size = writer.size
        storage.export_upload(file_path=str(path), file_name=name)
    return name, size, digest.hexdigest()
