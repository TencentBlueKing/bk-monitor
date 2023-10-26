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

import copy
import logging

from alarm_backends.service.alert.enricher.translator.base import TranslationField
from alarm_backends.service.alert.enricher.translator.bcs_cluster import (
    BcsClusterTranslator,
)
from alarm_backends.service.alert.enricher.translator.collect_config import (
    CollectingConfigTranslator,
)
from alarm_backends.service.alert.enricher.translator.corefile import CoreFileTranslator
from alarm_backends.service.alert.enricher.translator.index_set import (
    IndexSetTranslator,
)
from alarm_backends.service.alert.enricher.translator.nodata import NodataTranslator
from alarm_backends.service.alert.enricher.translator.result_table import (
    ResultTableTranslator,
)
from alarm_backends.service.alert.enricher.translator.service_instance import (
    ServiceInstanceTranslator,
)
from alarm_backends.service.alert.enricher.translator.topo import TopoNodeTranslator
from alarm_backends.service.alert.enricher.translator.uptimecheck import (
    UptimecheckConfigTranslator,
)
from alarm_backends.service.alert.enricher.translator.biz_name import BizNameTranslator

logger = logging.getLogger("alert.enricher")

INSTALLED_TRANSLATORS = (
    TopoNodeTranslator,
    UptimecheckConfigTranslator,
    CollectingConfigTranslator,
    ServiceInstanceTranslator,
    NodataTranslator,
    # 注意：ResultTableTranslator 必须要放到最后
    IndexSetTranslator,
    CoreFileTranslator,
    ResultTableTranslator,
    BcsClusterTranslator,
    BizNameTranslator,
)


class TranslatorFactory(object):
    def __init__(self, strategy):
        self.strategy = strategy
        self.translators = []

        for item in strategy["items"]:
            try:
                self._create_translators_by_item(item)
            except Exception as e:
                logger.exception("dimension translate error, reason：{}".format(e))

    def _create_translators_by_item(self, item):
        for translator_cls in INSTALLED_TRANSLATORS:
            translator = translator_cls(
                item=item,
                strategy=self.strategy,
            )
            if translator.is_enabled():
                self.translators.append(translator)

    def translate(self, data):
        data = copy.deepcopy(data)
        translated_data = {}
        for name, value in list(data.items()):
            translated_data[name] = TranslationField(name, value)
        for translator in self.translators:
            try:
                translated_data = translator.translate(translated_data)
            except Exception as e:
                logger.exception(
                    "dimension translate error, reason: {}. origin data: {}, middle data: {}".format(
                        e, data, translated_data
                    )
                )

        for name, value in list(translated_data.items()):
            translated_data[name] = value.to_dict()

        return translated_data
