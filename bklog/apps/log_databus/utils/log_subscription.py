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
"""

import inspect
import hashlib


def _count_md5(content):
    if content is None:
        return None
    m2 = hashlib.md5()
    if isinstance(content, str):
        m2.update(content.encode("utf8"))
    else:
        m2.update(content)
    return m2.hexdigest()


def count_md5(content, dict_sort=True, list_sort=True):
    if dict_sort and isinstance(content, dict):
        # dict的顺序受到hash的影响，所以这里先排序再计算MD5
        return count_md5(
            [(str(k), count_md5(content[k], dict_sort, list_sort)) for k in sorted(content.keys())],
            dict_sort,
            list_sort,
        )
    elif isinstance(content, (list, tuple)):
        content = (
            sorted([count_md5(k, dict_sort) for k in content])
            if list_sort
            else [count_md5(k, dict_sort, list_sort) for k in content]
        )
    elif callable(content):
        return make_callable_hash(content)
    return _count_md5(str(content))


def make_callable_hash(content):
    """
    计算callable的hash
    """
    if inspect.isclass(content):
        h = []
        for attr in [i for i in sorted(dir(content)) if not i.startswith("__")]:
            v = getattr(content, attr)
            h.append(count_md5(v))

        return _count_md5("".join(h))
    try:
        return _count_md5(content.__name__)
    except AttributeError:
        try:
            return _count_md5(content.func.__name__)
        except AttributeError:
            return _count_md5(str(content))
