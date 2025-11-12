"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.service.alert.enricher.translator.base import BaseTranslator, TranslationField
from constants.apm import ApmAlertHelper


class ApmTranslator(BaseTranslator):
    _helper: type[ApmAlertHelper] = ApmAlertHelper

    def is_enabled(self) -> bool:
        return self._helper.is_match(self.strategy)

    def translate(self, data: dict[str, TranslationField]) -> dict:
        for name, field in data.items():
            display_name: str = self._helper.get_tag_label(name)
            if display_name != name:
                # 展示值不一样时，认为成功找到别名，否则不设置，避免覆盖其他翻译器的处理结果。
                field.display_name = display_name
        return data
