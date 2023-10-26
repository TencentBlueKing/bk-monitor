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

import errno
import os

__implements__ = ["_copyxattr"]


# https://github.com/python/cpython/pull/13673/files
# :func:`shutil.copystat` now ignores :const:`errno.EINVAL` on :func:`os.setxattr`
# which may occur when copying files on filesystems without extended attributes support.

# https://bugs.python.org/issue24564#msg246278


if hasattr(os, "listxattr"):

    def _copyxattr(src, dst, *, follow_symlinks=True):  # noqa
        """Copy extended filesystem attributes from `src` to `dst`.

        Overwrite existing attributes.

        If `follow_symlinks` is false, symlinks won't be followed.

        """

        try:
            names = os.listxattr(src, follow_symlinks=follow_symlinks)
        except OSError as e:
            if e.errno not in (errno.ENOTSUP, errno.ENODATA, errno.EINVAL):
                raise
            return
        for name in names:
            try:
                value = os.getxattr(src, name, follow_symlinks=follow_symlinks)
                os.setxattr(dst, name, value, follow_symlinks=follow_symlinks)
            except OSError as e:
                if e.errno not in (errno.EPERM, errno.ENOTSUP, errno.ENODATA, errno.EINVAL):
                    raise


else:

    def _copyxattr(*args, **kwargs):
        pass
