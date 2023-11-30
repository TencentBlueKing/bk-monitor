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
import threading
from typing import List, Optional

# 默认的批量大小
DEFAULT_BULK_SIZE = 50


def bulk_handle(
    handler, data: List, bulk_size: Optional[int] = DEFAULT_BULK_SIZE, is_wait_finish: Optional[bool] = True
):
    """批量操作"""
    # 获取长度，用以进行分组
    count = len(data)
    chunk_size = count // bulk_size + 1 if count % bulk_size != 0 else int(count / bulk_size)
    # 分组
    chunks = [data[i : i + chunk_size] for i in range(0, count, chunk_size)]
    threads = []

    for chunk in chunks:
        t = threading.Thread(target=handler, args=(chunk,))
        t.start()
        threads.append(t)

    # 如果不需要等待，则直接返回
    if not is_wait_finish:
        return

    # 等待所有线程完成
    for t in threads:
        t.join()
