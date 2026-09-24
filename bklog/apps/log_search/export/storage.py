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
    ASYNC_APP_CODE,
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
