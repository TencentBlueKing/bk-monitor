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


import hashlib
import itertools
import random
import re
import socket

import arrow


def nothing_contextmgr(*args, **kwargs):
    yield


def is_ip(ci_name):
    try:
        socket.inet_aton(ci_name)
        return True
    except Exception:
        return False


def get_local_ip():
    """
    Returns the actual ip of the local machine.
    This code figures out what source address would be used if some traffic
    were to be sent out to some well known address on the Internet. In this
    case, a Google DNS server is used, but the specific address does not
    matter much.  No traffic is actually sent.

    stackoverflow上有人说用socket.gethostbyname(socket.getfqdn())
    但实测后发现有些机器会返回127.0.0.1
    """
    try:
        csock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        csock.connect(("8.8.8.8", 80))
        (addr, port) = csock.getsockname()
        csock.close()
        return addr
    except socket.error:
        return "127.0.0.1"


def split_list(raw_string):
    if isinstance(raw_string, (list, set)):
        return raw_string
    re_obj = re.compile(r"\s*[;,]\s*")
    return [x for x in re_obj.split(raw_string) if x]


def expand_list(obj_list):
    return list(itertools.chain.from_iterable(obj_list))


def remove_blank(objs):
    if isinstance(objs, (list, set)):
        return [str(obj) for obj in objs if obj]
    return objs


def remove_tag(text):
    """去除 html 标签"""
    tag_re = re.compile(r"<[^>]+>")
    return tag_re.sub("", text)


def get_random_id():
    return "{}{}".format(arrow.now().timestamp, random.randint(1000, 9999))


def _count_md5(content):
    if content is None:
        return None
    m2 = hashlib.md5()
    if isinstance(content, str):
        m2.update(content.encode("utf8"))
    else:
        m2.update(content)
    return m2.hexdigest()


def count_md5(content, dict_sort=True):
    if dict_sort and isinstance(content, dict):
        # dict的顺序受到hash的影响，所以这里先排序再计算MD5
        return count_md5([(str(k), count_md5(content[k])) for k in sorted(content.keys())])
    elif isinstance(content, (list, tuple)):
        content = sorted([count_md5(k) for k in content])
    elif isinstance(content, bytes):
        return _count_md5(content)
    return _count_md5(str(content))


def get_md5(content):
    if isinstance(content, list):
        return [count_md5(c) for c in content]
    else:
        return count_md5(content)
