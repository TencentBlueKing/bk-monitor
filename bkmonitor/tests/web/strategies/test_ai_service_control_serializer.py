"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.strategy.serializers import IntelligentDetectSerializer
from monitor_web.strategies.serializers import apply_intelligent_detect_bkfara_grey


class TestAIServiceControlSerializer:
    def test_intelligent_detect_serializer_should_keep_default_false(self):
        serializer = IntelligentDetectSerializer(data={"args": {}, "plan_id": 1})

        serializer.is_valid(raise_exception=True)

        assert serializer.validated_data["grey_to_bkfara"] is False

    def test_apply_intelligent_detect_bkfara_grey_should_enable_new_strategy(self):
        value = [
            {
                "algorithm_type": "IntelligentDetect",
                "algorithm_config": {"args": {}, "plan_id": 1, "grey_to_bkfara": False},
            }
        ]

        validated_value = apply_intelligent_detect_bkfara_grey(value, is_new_strategy=True)

        assert validated_value[0]["algorithm_config"]["grey_to_bkfara"] is True

    def test_apply_intelligent_detect_bkfara_grey_should_keep_existing_strategy(self):
        value = [
            {
                "algorithm_type": "IntelligentDetect",
                "algorithm_config": {"args": {}, "plan_id": 1, "grey_to_bkfara": False},
            }
        ]

        validated_value = apply_intelligent_detect_bkfara_grey(value, is_new_strategy=False)

        assert validated_value[0]["algorithm_config"]["grey_to_bkfara"] is False
