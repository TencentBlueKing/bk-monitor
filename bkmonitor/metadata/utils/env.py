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


import logging
import os

logger = logging.getLogger("metadata")


def get_env_list(env_prefix):
    """
    获取可以遍历的环境变量信息，并通过一个数组的方式返回
    例如，获取IP0 ~ IPn环境变量, 调用get_env_list(env_prefix="IP"), 返回["1.1.1.1", "2.2.2.2"]
    :param env_prefix: 环境变量前缀
    :return: ["info", "info"]
    """
    index = 0
    result = []
    while True:
        current_name = "{}{}".format(env_prefix, index)
        current_value = os.getenv(current_name)

        # 此轮已经不能再获取新的变量了，可以返回
        # 此处，我们相信变量不存在跳跃的情况
        if current_value is None:
            break

        result.append(current_value)
        index += 1

    logger.info("env->[{}] got total env count->[{}]".format(env_prefix, index))
    return result
