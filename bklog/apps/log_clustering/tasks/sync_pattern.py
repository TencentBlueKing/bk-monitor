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
from typing import List

from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab

from apps.log_clustering.constants import (
    CONTENT_PATTERN_INDEX,
    ORIGIN_LOG_INDEX,
    PATTERN_INDEX,
    PATTERN_SIGNATURE_INDEX,
)
from apps.log_clustering.exceptions import ModelReleaseNotFoundException
from apps.log_clustering.handlers.aiops.aiops_model.aiops_model_handler import (
    AiopsModelHandler,
)
from apps.log_clustering.models import AiopsSignatureAndPattern, ClusteringConfig
from apps.log_search.models import LogIndexSet
from apps.utils.task import high_priority_task


@periodic_task(run_every=crontab(minute="*/10"))
def sync_pattern():
    clustering_configs = ClusteringConfig.objects.filter(signature_enable=True, signature_pattern_rt="").values(
        "model_id", "model_output_rt", "index_set_id"
    )
    index_set_ids = set()
    for clustering_config in clustering_configs:
        index_set_ids.add(clustering_config["index_set_id"])

    index_set_id_list = LogIndexSet.objects.filter(is_active=True, index_set_id__in=index_set_ids).values_list(
        "index_set_id", flat=True
    )
    model_ids = set()
    model_output_rts = set()
    for clustering_config in clustering_configs:
        if clustering_config["index_set_id"] not in index_set_id_list:
            continue
        model_id = clustering_config["model_id"]
        model_output_rt = clustering_config["model_output_rt"]
        if model_output_rt and model_output_rt not in model_output_rts:
            model_output_rts.add(model_output_rt)
            sync.delay(model_output_rt=model_output_rt)
        elif not model_output_rt and model_id and model_id not in model_ids:
            model_ids.add(model_id)
            sync.delay(model_id=model_id)


@high_priority_task(ignore_result=True)
def sync(model_id=None, model_output_rt=None):
    if model_id:
        try:
            release_id = AiopsModelHandler().get_latest_released_id(model_id=model_id)
        except ModelReleaseNotFoundException:
            return

        content = AiopsModelHandler().aiops_release_model_release_id_model_file(
            model_id=model_id, model_release_id=release_id
        )["file_content"]

    elif model_output_rt:
        model_id = model_output_rt
        content = AiopsModelHandler().model_output_rt_model_file(model_output_rt=model_output_rt)["file_content"]

    else:
        return

    # pickle 解码
    content = AiopsModelHandler.pickle_decode(content=content)

    patterns = get_pattern(content)
    objects_to_create, objects_to_update = make_signature_objects(patterns=patterns, model_id=model_id)
    AiopsSignatureAndPattern.objects.bulk_create(objects_to_create, batch_size=500)
    AiopsSignatureAndPattern.objects.bulk_update(
        objects_to_update, fields=["pattern", "origin_pattern"], batch_size=500
    )


def get_pattern(content) -> list:
    """
    content demo:
    [
        '...',
        {
            0.1: [
                ['if', 'checker.check'],
                3903,
                ['if', 'checker.check', '*', Variable(name="ip", value='127.0.0.1')],
                ['if checker.check():', 'if checker.check()'],
                [282. 1877],
                27886975249790003104399390262688492018705644758766193963474214767849400520551
            ]
        },
        '...',
        '...'
    ]
    sensitive_pattern [List]:
    - representative tokens: 符合pattern的其中一个分词
    - numbers: 属于该pattern的日志数量
    - pattern: 聚类模式
    - raw_log: 所有原始log,list
    - log_index： 所有原始log的index
    - log_signature: 聚类模型signature
    """
    patterns = []
    if isinstance(content, list):
        content = content[CONTENT_PATTERN_INDEX]
    for _, sensitive_patterns in content.items():
        for sensitive_pattern in sensitive_patterns:
            signature = sensitive_pattern[PATTERN_SIGNATURE_INDEX]
            if not sensitive_pattern[ORIGIN_LOG_INDEX]:
                pattern_list = []
                for pattern in sensitive_pattern[PATTERN_INDEX]:
                    if hasattr(pattern, "name"):
                        pattern_list.append("#{}#".format(pattern.name))
                        continue
                    pattern_list.append(str(pattern))
                patterns.append(
                    {
                        "signature": str(signature),
                        "pattern": " ".join(pattern_list),
                        "origin_pattern": " ".join(pattern_list),
                    }
                )
                continue

            origin_log = sensitive_pattern[ORIGIN_LOG_INDEX][0]
            if isinstance(origin_log, list):
                origin_log = origin_log[0]
            pattern_str = ""
            pattern_list = []
            for pattern in sensitive_pattern[PATTERN_INDEX]:
                if hasattr(pattern, "name"):
                    value = pattern.value
                    name = f"#{pattern.name}#"
                elif isinstance(pattern, (tuple, list)):
                    value = pattern[-1]
                    name = f"#{pattern[-2]}#"
                else:
                    value = pattern
                    name = pattern
                pattern_list.append(name)
                idx = origin_log.find(value)
                if idx == -1:
                    continue
                pattern_str += origin_log[0:idx]
                pattern_str += name
                origin_log = origin_log[idx + len(value) :]
            pattern_str += origin_log
            patterns.append(
                {"signature": str(signature), "pattern": pattern_str, "origin_pattern": " ".join(pattern_list)}
            )
    return patterns


def make_signature_objects(patterns, model_id) -> [List[AiopsSignatureAndPattern], List[AiopsSignatureAndPattern]]:
    """
    生成 signature 对象
    :param patterns:
    :param model_id:
    :return:
    """
    origin_signature_map = {pattern["signature"]: pattern for pattern in patterns}
    existed_signature_map = {obj.signature: obj for obj in AiopsSignatureAndPattern.objects.filter(model_id=model_id)}

    objects_to_create = []
    objects_to_update = []

    for origin_signature, origin_pattern in origin_signature_map.items():
        if origin_signature not in existed_signature_map:
            # 不存在的，创建一个新对象
            objects_to_create.append(
                AiopsSignatureAndPattern(
                    model_id=model_id,
                    signature=origin_signature,
                    pattern=origin_pattern["pattern"],
                    origin_pattern=origin_pattern["origin_pattern"],
                )
            )
        else:
            # 已经存在的，只更新对象中的 pattern 字段
            signature_obj = existed_signature_map[origin_signature]
            signature_obj.pattern = origin_pattern["pattern"]
            # 保留原始pattern 用于不同索引之间的数据同步
            signature_obj.origin_pattern = origin_pattern["origin_pattern"]
            objects_to_update.append(signature_obj)
    return objects_to_create, objects_to_update
