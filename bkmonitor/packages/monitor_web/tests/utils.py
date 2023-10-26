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


from six.moves import range


def equal_value(data1, data2, ignore=[]):
    if isinstance(data1, dict):
        ignore_dict = {}
        for item in ignore:
            i_split = item.split(".")
            if i_split[0] in ignore_dict and len(ignore_dict[i_split[0]]) == 0:
                continue

            x = ignore_dict.setdefault(i_split[0], [])
            if len(i_split) > 1:
                x.append(".".join(i_split[1:]))

        for k, v in data1.items():
            if k in ignore_dict and ignore_dict[k] == []:
                continue
            try:
                equal_value(v, data2[k], ignore_dict.get(k, []))
            except KeyError:
                assert data1 == data2
    elif isinstance(data1, list):
        for i in range(len(data1)):
            try:
                equal_value(data1[i], data2[i], ignore)
            except IndexError:
                assert data1 == data2
    else:
        assert data1 == data2
