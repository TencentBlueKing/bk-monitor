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

import os

from django.conf import settings

from apps.constants import RemoteStorageType
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_search.constants import (
    ASYNC_APP_CODE,
    ASYNC_EXPORT_EXPIRED,
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_STORAGE_TYPE,
)
from apps.utils.remote_storage import NfsStorage, StorageType


def build_storage():
    """
    构建产物存储实例。

    直接复用旧异步导出链路的开关与封装（COS/NFS/BKRepo 三选一），
    分片导出不新增存储配置，也不新增一种后端。
    """
    toggle = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config
    storage_type = toggle.get(FEATURE_ASYNC_EXPORT_STORAGE_TYPE)
    storage = StorageType.get_instance(storage_type)
    if not storage_type or storage_type == RemoteStorageType.NFS.value:
        return storage(settings.EXTRACT_SAAS_STORE_DIR)
    if storage_type == RemoteStorageType.BKREPO.value:
        return storage(expired=ASYNC_EXPORT_EXPIRED)
    return storage(
        toggle.get("qcloud_secret_id"),
        toggle.get("qcloud_secret_key"),
        toggle.get("qcloud_cos_region"),
        toggle.get("qcloud_cos_bucket"),
        ASYNC_EXPORT_EXPIRED,
    )


def artifact_name(job, part_no):
    """
    分片产物名；同时作为对象存储里的对象键。

    必须是 (job, part_no) 的纯函数：重试、重复投递和超时回收都会重新执行同一个分片，
    确定性命名让后一次执行覆盖同一个对象，而不是留下没有任何引用的孤儿产物。
    """
    return f"{ASYNC_APP_CODE}_{job.index_set_id}_{job.pk}_{part_no}.tar.gz"


def manifest_name(job):
    return f"{ASYNC_APP_CODE}_{job.index_set_id}_{job.pk}_manifest.json"


def upload(storage, file_path, file_name):
    return storage.export_upload(file_path=str(file_path), file_name=file_name)


def download_url(storage, url_path, file_name, ttl):
    return storage.generate_download_url(url_path=url_path, file_name=file_name, expired=ttl)


def supports_artifact_cleanup(storage):
    """只有 NFS 的产物是共享目录里可直接删除的文件；对象存储一期依赖桶的生命周期策略。"""
    return isinstance(storage, NfsStorage)


def remove_local_artifact(storage, file_name):
    """删除 NFS 共享目录里的产物文件，返回是否真的删掉了。"""
    if not supports_artifact_cleanup(storage) or not file_name:
        return False
    path = os.path.join(settings.EXTRACT_SAAS_STORE_DIR, file_name)
    if not os.path.isfile(path):
        return False
    os.remove(path)
    return True
