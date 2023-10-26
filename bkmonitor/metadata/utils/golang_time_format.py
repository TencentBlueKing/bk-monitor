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


import re

DATE_FORMAT_RE = re.compile(r"(((?P<days>\d+)d)?)(((?P<hours>\d+)h)?)(((?P<min>\d+)m)?)(((?P<sec>\d+)s)?)")


def trans_time_format(date_foramt):
    """
    将传入的date_format转换为golang中的time.Duration的string内容输出
    :param date_format: '30d24h3m10s'
    :return:
    """

    match_result = DATE_FORMAT_RE.match(date_foramt)
    # 如果匹配失败的，直接返回0s
    if match_result is None:
        return "0s"

    match_group_dict = match_result.groupdict(default="0")
    days = int(match_group_dict.get("days"))
    hours = int(match_group_dict.get("hours"))
    min = int(match_group_dict.get("min"))
    sec = int(match_group_dict.get("sec"))

    # 最大的单位是days，所以需要和hour合并在一起
    final_hours = days * 24 + hours

    final_result = ""
    if final_hours:
        final_result = "{}h".format(final_hours)

    # 如果hour已经有内容，或者min不为空，都需要增加min的内容
    if final_result or min:
        final_result = "{}{}m".format(final_result, min)

    # sec是无论如何都需要添加的
    final_result = "{}{}s".format(final_result, sec)

    return final_result
