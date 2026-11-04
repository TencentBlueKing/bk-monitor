# -*- coding: utf-8 -*-
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
from apps.log_desensitize.exceptions import DesensitizeDataErrorException


def expand_nested_data(data: dict):
    """
    递归将data中的object类型字段展开{"aaa": {"aa": 1, "bb": 2}} -> {"aaa.aa": 1, "aaa.bb": 2}
    """
    try:
        res_data = dict()

        def _expand(_data: dict, key: str = ""):
            for _k, _v in _data.items():
                _key = _k if not key else "{}.{}".format(key, _k)
                if not isinstance(_v, dict):
                    res_data[_key] = _v
                else:
                    _expand(_data[_k], _key)

        _expand(data)
        return res_data
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def merge_nested_data(data: dict):
    """
    将data中的object类型字段合并{"aaa.aa": 1, "aaa.bb": 2} -> {"aaa": {"aa": 1, "bb": 2}}
    """
    try:
        merged_data = {}
        for key, value in data.items():
            keys = key.split('.')
            current = merged_data
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value

        return merged_data
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))
