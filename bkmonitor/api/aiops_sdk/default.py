"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from core.drf_resource import APIResource


class SdkResource(APIResource):
    TIMEOUT = 300
    METRIC_REPORT_NOW = False
    ignore_error_msg_list = ["SDK模型预测历史依赖"]

    # 模块名
    module_name = "aiops_sdk"


class SdkPredictResource(APIResource):
    """
    SDK执行预测逻辑
    """

    class RequestSerializer(serializers.Serializer):
        data = serializers.ListField(required=True, child=serializers.DictField())
        dimensions = serializers.DictField(required=False, default=dict())
        predict_args = serializers.DictField(required=False, default=dict())
        interval = serializers.IntegerField(default=60)
        extra_data = serializers.DictField(default=dict())
        serving_config = serializers.DictField(default=dict())

    action = "/api/aiops/default/"
    method = "POST"


class SdkGroupPredictResource(APIResource):
    """
    SDK执行分组预测逻辑
    """

    class RequestSerializer(serializers.Serializer):
        group_data = serializers.ListField(required=True, child=serializers.DictField())
        predict_args = serializers.DictField(required=False, default=dict())
        interval = serializers.IntegerField(default=60)

    action = "/api/aiops/group_predict/"
    method = "POST"


class DependencyDataSerializer(serializers.Serializer):
    data = serializers.ListField(child=serializers.DictField())
    dimensions = serializers.DictField(default=dict())
    partition = serializers.CharField(allow_blank=True, default=None)


class SdkInitDependResource(APIResource):
    """
    SDK初始化历史依赖
    """

    class RequestSerializer(serializers.Serializer):
        dependency_data = serializers.ListField(child=DependencyDataSerializer())

    action = "/api/aiops/init_depend/"
    method = "POST"


class TfSdkResource(SdkResource):
    # 时序预测远程访问地址
    base_url = "http://bk-aiops-serving-tf:8000"


class TfPredictResource(TfSdkResource, SdkPredictResource):
    """时序预测SDK执行时序预测逻辑."""

    pass


class TfInitDependResource(TfSdkResource, SdkInitDependResource):
    """时序预测SDK初始化历史依赖."""

    pass


class TfGroupPredictResource(TfSdkResource, SdkGroupPredictResource):
    """时序预测SDK执行分组预测."""

    pass


class KpiSdkResource(SdkResource):
    # 智能异常检测远程访问地址
    base_url = "http://bk-aiops-serving-kpi:8000"


class KpiPredictResource(KpiSdkResource, SdkPredictResource):
    """异常检测SDK执行时序预测逻辑."""

    pass


class KpiInitDependResource(KpiSdkResource, SdkInitDependResource):
    """异常检测SDK初始化历史依赖."""

    pass


class KpiGroupPredictResource(KpiSdkResource, SdkGroupPredictResource):
    """异常检测SDK执行分组预测."""

    pass


class AcdSdkResource(SdkResource):
    # 离群检测远程访问地址
    base_url = "http://bk-aiops-serving-acd:8000"


class AcdPredictResource(AcdSdkResource, SdkPredictResource):
    """离群检测SDK执行时序预测逻辑."""

    pass


class AcdInitDependResource(AcdSdkResource, SdkInitDependResource):
    """离群检测SDK初始化历史依赖."""

    pass


class AcdGroupPredictResource(AcdSdkResource, SdkGroupPredictResource):
    """离群检测SDK执行分组预测."""

    pass
