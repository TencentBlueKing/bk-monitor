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

from bkmonitor.documents import ALL_DOCUMENTS

logger = logging.getLogger("bkmonitor.documents")


def rollover_indices():
    """
    索引轮转
    """
    for index in ALL_DOCUMENTS:
        try:
            new_index_name, alias = index.rollover()
            if not new_index_name:
                msg = "[ES ILM] index(%s) check rollover finished, nothing to do" % index.Index.name
            else:
                msg = "[ES ILM] index({}) check rollover finished, create index({}), alias({})".format(
                    index.Index.name, new_index_name, alias
                )
            logger.info(msg)
            print(msg)
        except Exception as e:
            msg = "[ES ILM] index({}) rollover failed: {}".format(index.Index.name, e)
            logger.exception(msg)
            print(msg)


def clear_expired_indices():
    """
    索引清理
    """
    for index in ALL_DOCUMENTS:
        try:
            result = index.clear_expired_index()
            logger.info("[ES ILM] index(%s) clear expired success: %s", index.Index.name, result)
        except Exception as e:
            logger.exception("[ES ILM] index(%s) clear expired failed: %s", index.Index.name, e)
