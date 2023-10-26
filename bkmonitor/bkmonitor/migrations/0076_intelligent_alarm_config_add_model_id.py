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

from django.db import migrations

# from bkmonitor.dataflow.constant import VisualType
# from bkmonitor.dataflow.task.intelligent_detect import StrategyIntelligentModelDetectTask


def intelligent_alarm_config_add_model_id(apps, *args, **kwargs):
    pass
    # AlgorithmModel = apps.get_model("bkmonitor", "AlgorithmModel")
    # for algorithm in AlgorithmModel.objects.filter(type="IntelligentDetect"):
    #     algorithm_conf = algorithm.config
    #     # 保持幂等性
    #     if algorithm_conf.get("bkdata_model_id"):
    #         continue
    #     anomaly_detect_direct = algorithm_conf.get("anomaly_detect_direct") or "all"
    #     sensitivity_value = algorithm_conf.get("sensitivity_value") or 0
    #     args = {
    #         "alert_upward": int(anomaly_detect_direct in ["ceil", "all"]),
    #         "alert_down": int(anomaly_detect_direct in ["floor", "all"]),
    #         "sensitivity": float(sensitivity_value) / 100,
    #     }
    #     algorithm.config = {
    #         "bkdata_model_id": StrategyIntelligentModelDetectTask.MODEL_ID,
    #         "visual_type": VisualType.SCORE,
    #         "args": args,
    #     }
    #     algorithm.save()
    #
    # QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    # for query_config in QueryConfigModel.objects.filter(config__has_key="intelligent_detect"):
    #     query_config.config["intelligent_detect"]["extend_fields"] = {"values": ["is_anomaly", "extra_info"]}
    #     if "bkdata_model_id" not in query_config.config["intelligent_detect"]:
    #         query_config.config["intelligent_detect"]["bkdata_model_id"] = StrategyIntelligentModelDetectTask.MODEL_ID
    #     query_config.save()


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0075_merge_20211207_1142"),
    ]

    operations = [
        migrations.RunPython(intelligent_alarm_config_add_model_id),
    ]
