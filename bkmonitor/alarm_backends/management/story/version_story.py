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
from distutils.version import StrictVersion

from django.conf import settings

from alarm_backends.management.story.base import BaseStory, CheckStep, Problem, register_step, register_story


@register_story()
class VersionStory(BaseStory):
    name = "Version Requirements Check"


class VersionCheckStep(CheckStep):
    module_name = ""
    version_require = ""

    @property
    def name(self):
        return f"check {self.module_name} version"  # noqa

    def version(self):
        raise NotImplementedError

    def check(self):
        now_version = self.version()
        if self.version_require and now_version:
            if StrictVersion(self.version_require) > StrictVersion(now_version):
                p = VersionProblem(
                    f"{self.module_name} version require {self.version_require},"
                    f" current version {now_version} is too low",
                    self.story,
                )
                return p
        else:
            self.story.info(f"{self.module_name} version: {now_version or 'unknown'}")


@register_step(VersionStory)
class SaaSVersion(VersionCheckStep):
    module_name = "SaaS"

    def version(self):
        return settings.SAAS_VERSION


@register_step(VersionStory)
class BackendVersion(VersionCheckStep):
    module_name = "Backend"

    def version(self, peaceful=True):
        version = ""
        try:
            with open(os.path.join(settings.BASE_DIR, "VERSION")) as vfd:
                version = vfd.read().strip()
        except Exception as e:
            self.story.warning("get version info error: {}".format(e))
        finally:
            settings.BACKEND_VERSION = version
            return version


class VersionProblem(Problem):
    pass
