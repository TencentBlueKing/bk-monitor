# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""


def divide_biscuit(iterator, interval):
    """分段"""
    for i in range(0, len(iterator), interval):
        yield iterator[i : i + interval]


def balanced_biscuit(input_list, num_splits):
    """切分"""
    split_size = len(input_list) // num_splits
    remainder = len(input_list) % num_splits
    result = []
    current_index = 0

    for i in range(num_splits):
        current_split_size = split_size + int(i < remainder)
        result.append(input_list[current_index : current_index + current_split_size])
        current_index += current_split_size

    return result


def group_by(iterators, get_key):
    res = {}
    for item in iterators:
        key = get_key(item)
        if not key:
            continue

        if key in res:
            res[key].append(item)
        else:
            res[key] = [item]

    return res
