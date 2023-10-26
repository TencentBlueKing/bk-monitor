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


import six

__all__ = [
    "patch_all",
    "patch_module",
]


def patch_module(name, items=None):
    """
    The codes below comes from gevent.monkey.patch_module()
    """
    rt_module = __import__("patches." + name)
    target_module = __import__(name)
    for i, submodule in enumerate(name.split(".")):
        rt_module = getattr(rt_module, submodule)
        if i:
            target_module = getattr(target_module, submodule)
    items = items or getattr(rt_module, "__implements__", None)
    if items is None:
        raise AttributeError("%r does not have __implements__" % rt_module)

    for attr in items:
        setattr(target_module, attr, getattr(rt_module, attr))
    return target_module


def patch_all(targets=None):
    """
    targets = {
        'celery.utils.log': None,
    }
    """
    if not isinstance(targets, dict):
        targets = {}

    for module, items in six.iteritems(targets):
        patch_module(module, items=items)
