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

import humanize
import six
from babel import support
from django.utils import timezone, translation

logger = logging.getLogger("utils")


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class I18N(six.with_metaclass(Singleton, object)):
    def __init__(self):
        # 全局唯一, 修改后可更改语言, 时区
        self.bk_biz_id = None

        from django.conf import settings

        self.default_locale = settings.DEFAULT_LOCALE
        self.default_timezone = settings.TIME_ZONE

        self.translations = {}
        self.domain = None
        translation.activate(self.get_locale())
        timezone.activate(self.get_timezone())

    def set_biz(self, bk_biz_id):
        """change biz method"""
        self.bk_biz_id = bk_biz_id
        translation.activate(self.get_locale())
        timezone.activate(self.get_timezone())

    @property
    def translation_directories(self):
        """翻译文件夹"""
        from django.conf import settings

        if settings.LOCALE_PATHS:
            return settings.LOCALE_PATHS
        else:
            return [
                os.path.join(settings.BASE_DIR, "locale"),
            ]

    @staticmethod
    def locale_best_match(locale):
        """兼容不同编码"""
        # cc接口变更，导致返回值变成"1"
        if locale.lower() in ["zh", "zh_cn", "zh-cn", "1", "zh-hans"]:
            humanize.i18n.activate("zh_CN", path="bkmonitor/utils/humanize_locale")
            return "zh_Hans_CN"

        humanize.i18n.deactivate()
        return "en"

    def get_locale(self):
        """
        根据业务ID获取语言
        """
        from alarm_backends.core.cache.cmdb.business import BusinessManager

        if not self.bk_biz_id:
            return self.default_locale

        business = BusinessManager.get(self.bk_biz_id)

        if business:
            return self.locale_best_match(business.language)
        else:
            return self.default_locale

    def get_timezone(self):
        """
        根据业务ID获取时区
        """
        from alarm_backends.core.cache.cmdb.business import BusinessManager

        if not self.bk_biz_id:
            return self.default_timezone

        business = BusinessManager.get(self.bk_biz_id)

        if business:
            return business.time_zone
        else:
            return self.default_timezone

    def get_translations(self):
        """
        get translation on the fly
        """
        locale = self.get_locale()
        if locale not in self.translations:
            translations = support.Translations()

            for dirname in self.translation_directories:
                catalog = support.Translations.load(
                    dirname,
                    [locale],
                    self.domain,
                )
                translations.merge(catalog)
                if hasattr(catalog, "plural"):
                    translations.plural = catalog.plural
            logger.info("load translations, %s=%s", locale, translations)
            self.translations[locale] = translations

        return self.translations[locale]


i18n = I18N()
