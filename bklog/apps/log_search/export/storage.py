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

from apps.constants import RemoteStorageType
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_search.constants import (
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_EXTERNAL,
    FEATURE_ASYNC_EXPORT_STORAGE_TYPE,
)
from apps.utils.remote_storage import StorageType


class UnsupportedExportStorage(Exception):
    """分片导出只支持对象存储。"""


SUPPORTED_STORAGE_TYPES = (RemoteStorageType.COS.value, RemoteStorageType.BKREPO.value)
OBJECT_PREFIX = "exports"


def build_storage(external=False):
    """构建产物存储实例；外部版任务读 feature_async_export_external，内部任务读 feature_async_export。"""
    toggle_name = FEATURE_ASYNC_EXPORT_EXTERNAL if external else FEATURE_ASYNC_EXPORT_COMMON
    config = FeatureToggleObject.toggle(toggle_name).feature_config
    storage_type = config.get(FEATURE_ASYNC_EXPORT_STORAGE_TYPE)
    if storage_type not in SUPPORTED_STORAGE_TYPES:
        raise UnsupportedExportStorage(f"分片导出不支持当前存储类型 {storage_type}")
    storage = StorageType.get_instance(storage_type)
    if storage_type == RemoteStorageType.BKREPO.value:
        return storage()
    return storage(
        config.get("qcloud_secret_id"),
        config.get("qcloud_secret_key"),
        config.get("qcloud_cos_region"),
        config.get("qcloud_cos_bucket"),
        0,
    )


def job_object_prefix(job_id):
    return f"{OBJECT_PREFIX}/{job_id}/"


def artifact_name(job, part, attempts):
    """分片产物名，同时作为对象键。必须含认领序号：一个键只能有一个执行在写。"""
    return f"{job_object_prefix(job.pk)}parts/{part.pk}/attempt-{attempts}.tar.gz"


def manifest_name(job):
    return f"{job_object_prefix(job.pk)}manifest.json"
