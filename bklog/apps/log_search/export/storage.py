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


# NFS 的下载链接是应用内下载接口加固定密文：没有签名有效期，也无法按需刷新，
# 与分片导出按需签发临时链接的契约不符，因此只接受对象存储。
SUPPORTED_STORAGE_TYPES = (RemoteStorageType.COS.value, RemoteStorageType.BKREPO.value)


def build_storage(external=False):
    """构建产物存储实例；外部版任务读 feature_async_export_external，内部任务读 feature_async_export。"""
    toggle_name = FEATURE_ASYNC_EXPORT_EXTERNAL if external else FEATURE_ASYNC_EXPORT_COMMON
    config = FeatureToggleObject.toggle(toggle_name).feature_config
    storage_type = config.get(FEATURE_ASYNC_EXPORT_STORAGE_TYPE)
    if storage_type not in SUPPORTED_STORAGE_TYPES:
        raise UnsupportedExportStorage(
            f"分片导出仅支持 COS / BKREPO 存储，当前配置 {toggle_name}.{FEATURE_ASYNC_EXPORT_STORAGE_TYPE}={storage_type!r}"
        )
    storage = StorageType.get_instance(storage_type)
    # 下载链接的有效期由 download_link 按产物剩余保留时间逐次签发，存储实例上的默认有效期
    # 不会生效；CosStorage 的构造参数没有默认值，这里显式给 0 表示不设置默认有效期。
    if storage_type == RemoteStorageType.BKREPO.value:
        return storage()
    return storage(
        config.get("qcloud_secret_id"),
        config.get("qcloud_secret_key"),
        config.get("qcloud_cos_region"),
        config.get("qcloud_cos_bucket"),
        0,
    )


# 分片导出产物统一放在该前缀下：桶生命周期规则和任务级清理都按这个前缀匹配
OBJECT_PREFIX = "exports"


def job_object_prefix(job_id):
    """任务产物前缀：包含该任务的全部分片对象与清单。"""
    return f"{OBJECT_PREFIX}/{job_id}/"


def artifact_name(job, part, attempts):
    """
    分片产物名；同时作为对象存储里的对象键。

    键必须包含认领序号 attempts：同一个分片的每次认领（重复投递、超时回收、重试）都会递增
    attempts，因此一个键只会有一个执行在写。后一次执行写自己的键，不会覆盖已经被 fence
    接受并发布的产物；提交被拒绝的执行由 Worker 清掉自己的键，进程崩溃残留的对象交给
    前缀生命周期兜底。
    """
    return f"{job_object_prefix(job.pk)}parts/{part.pk}/attempt-{attempts}.tar.gz"


def manifest_name(job):
    return f"{job_object_prefix(job.pk)}manifest.json"


def upload(storage, file_path, file_name):
    return storage.export_upload(file_path=str(file_path), file_name=file_name)


def delete_artifact(storage, file_name):
    """删除产物对象；对象不存在时视为已清理。"""
    return storage.delete_file(file_name)
