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


import os

import six
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string


class Command(BaseCommand):
    help = "Generate configuration file for alarm_backends."

    configs = {
        os.path.join(settings.BASE_DIR, "alarm_backends/conf/supervisord.conf"): "config/supervisor.tmpl",
    }

    # options
    _ENVIRONMENT_ = "development"
    _PLATFORM_ = "enterprise"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "--environment",
            choices=["development", "testing", "production"],
            help="environment name (default empty).",
        )
        parser.add_argument(
            "--platform",
            choices=["enterprise", "community"],
            help="platform name (default empty).",
        )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        self._ENVIRONMENT_ = settings.ENVIRONMENT
        self._PLATFORM_ = settings.PLATFORM

    def handle(self, *args, **options):
        for option, value in six.iteritems(options):
            if option not in ("no_color", "pythonpath", "settings", "traceback", "verbosity") and value is not None:
                attr = "_{}_".format(option.upper())
                setattr(self, attr, options[option])

        context = {
            "settings": settings,
            "ENVIRONMENT": self._ENVIRONMENT_,
            "PLATFORM": self._PLATFORM_,
        }

        for filepath, template_name in six.iteritems(self.configs):
            dirname = os.path.dirname(filepath)
            if not os.path.exists(dirname):
                try:
                    os.makedirs(dirname)
                except:  # noqa
                    pass
            with open(filepath, "w+") as f:
                f.write(render_to_string(template_name, context))
