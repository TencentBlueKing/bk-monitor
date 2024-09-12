# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from bkstorages.backends.bkrepo import BKGenericRepoClient, BKRepoStorage
from django.conf import settings
from django.core.cache import cache

from constants.common import LOGO_IMAGE_TIMEOUT


class BKCacheRepoClient(BKGenericRepoClient):
    def upload_fileobj(self, fh, key: str, allow_overwrite: bool = True, **kwargs):
        """上传通用制品文件并把文件记录到django的cache中

        :param BinaryIO fh: 文件句柄
        :param str key: 文件完整路径
        :param bool allow_overwrite: 是否覆盖已存在文件
        """
        cache_key = f"cache_repo_{self.project}_{self.bucket}_{key}"
        super().upload_fileobj(fh, key, allow_overwrite, **kwargs)
        fh.seek(0)
        cache_content = fh.read()
        cache.set(cache_key, cache_content, timeout=LOGO_IMAGE_TIMEOUT)

    def download_fileobj(self, key: str, fh, *args, **kwargs):
        """从django的cache读区制品文件内容或者从制品库下载通用制品文件

        :param str key: 文件完整路径
        :param IO fh: 文件句柄
        """
        cache_key = f"cache_repo_{self.project}_{self.bucket}_{key}"
        cache_result = cache.get(cache_key)
        if not cache_result:
            super().download_fileobj(key, fh, *args, **kwargs)
            fh.seek(0)
            cache_result = fh.read()
            cache.set(cache_key, cache_result, timeout=LOGO_IMAGE_TIMEOUT)
            fh.seek(0)
        else:
            fh.write(cache_result)

        return cache_result


class BKCacheRepoStorage(BKRepoStorage):
    """基于蓝鲸制品库和Django Cache封装的带有缓存能力的文件存储器."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = BKCacheRepoClient(
            bucket=self.client.bucket,
            project=self.client.project,
            endpoint_url=self.client.endpoint_url,
            username=self.client.username,
            password=self.client.password,
        )


def get_default_image_storage():
    if getattr(settings, "USE_CEPH", False):
        return BKCacheRepoStorage

    return None
