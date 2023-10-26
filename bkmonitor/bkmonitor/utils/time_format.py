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
import math

LEVELS = [
    ("w", 7 * 24 * 60 * 60),
    ("d", 24 * 60 * 60),
    ("h", 60 * 60),
    ("m", 60),
    ("s", 1),
]


def duration_string(i: int = 0) -> str:
    """
    传入秒数，转化成字符串（单时间单位，如2w、7d、23h、15m、1s)
    :param i:
    :return:
    """
    if i == 0 or type(i) != int:
        return "0s"

    nec = False
    if i < 0:
        nec = True
        i = 0 - i

    result = ""
    if nec:
        result += "-"

    LEVELS.sort(key=lambda x: x[1], reverse=True)
    for _ in LEVELS:
        v = i % _[1]
        if v == 0:
            result += "{}{}".format(i // _[1], _[0])
            break
    return result


def parse_duration(s: str = "") -> int:
    """
    将传入的字符串，转化为秒级整数，支持：[-+] w, d, h, m, s
    例如："5m", "-2.5h", "1w3d5h10m10s"
    :param s:
    :return:
    """

    def add_seconds(cv: str = "", cs: int = 0) -> int:
        if cv == "":
            return 0
        try:
            return math.floor(float(cv) * cs)
        except ValueError:
            return 0

    # 处理 [-+] 符号
    neg = False
    if s != "":
        if s[0] == '-' or s[0] == '+':
            neg = s[0] == '-'
            s = s[1:]

    if s == "" or s == "0":
        return 0

    # 处理时间
    v = ""
    result = 0
    for i in s:
        if i == '.' or '0' <= i <= '9':
            v += i
        else:
            check = False
            for _ in LEVELS:
                if i == _[0]:
                    check = True
                    # 单位前没有数字
                    if v == "":
                        return 0
                    result += add_seconds(v, _[1])
                    v = ""
            # 无效单位
            if not check:
                return 0
    if neg:
        result = 0 - result
    return result
