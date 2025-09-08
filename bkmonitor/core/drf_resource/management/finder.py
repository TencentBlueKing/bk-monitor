# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import logging
import os

from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles.finders import BaseFinder

from bkmonitor.utils.text import path_to_dotted
from core.drf_resource.management.exceptions import ErrorSettingsWithResourceDirs

logger = logging.getLogger(__name__)


DEFAULT_API_DIR = "api"
DEFAULT_RESOURCE_DIRS = []


API_DIR = getattr(settings, "API_DIR", DEFAULT_API_DIR)
RESOURCE_DIRS = getattr(settings, "RESOURCE_DIRS", DEFAULT_RESOURCE_DIRS)
if API_DIR not in RESOURCE_DIRS:
    RESOURCE_DIRS.append(API_DIR)


class ResourceFinder(BaseFinder):
    def __init__(self, app_names=None, *args, **kwargs):
        # Mapping of app names to resource modules
        self.resource_path = []
        app_path_directories = []
        app_configs = apps.get_app_configs()
        if app_names:
            app_names = set(app_names)
            app_configs = [ac for ac in app_configs if ac.name in app_names]

        for app_config in app_configs:
            self.resource_path += self.find(app_config.path, root_path=os.path.dirname(app_config.path))
            app_path_directories.append(app_config.path)

        for path in RESOURCE_DIRS:
            search_path = os.path.join(settings.BASE_DIR, path)
            if search_path in app_path_directories:
                continue

            self.resource_path += self.find(search_path, from_settings=True)

        self.resource_path.sort()
        self.found()

    def found(self):
        p_list = []
        for p in self.resource_path:
            p_list.append(ResourcePath(p))

        self.resource_path = p_list

    def list(self, ignore_patterns):
        """
        List all resource path.
        """
        for path in self.resource_path:
            yield path.path, path.status

    def find(self, path, root_path=None, from_settings=False):
        """
        Looks for resource module in the app directories.
        if recursive is True, recursive traversal directory
        """
        matches = set()
        if not path.startswith(settings.BASE_DIR):
            if from_settings:
                raise ErrorSettingsWithResourceDirs("RESOURCE_DIRS settings error")
            return []

        for root, dirs, files in sorted(os.walk(path)):
            if os.path.basename(root) == "resources":
                relative_path = os.path.relpath(os.path.dirname(root), root_path or settings.BASE_DIR)
                matches.add(path_to_dotted(relative_path))
                continue

            for file_path in files:
                file_name = os.path.basename(file_path)
                base_file_name, ext_name = os.path.splitext(file_name)
                if ext_name not in [".py", ".pyc", ".pyo"]:
                    continue

                if base_file_name in ["resources", "default"]:
                    relative_path = os.path.relpath(root, root_path or settings.BASE_DIR)
                    matches.add(path_to_dotted(relative_path))
                    continue

        return matches


class ResourceStatus(object):
    # 待加载
    unloaded = "unloaded"
    # 加载成功
    loaded = "loaded"
    # 忽略
    ignored = "ignored"
    # 加载错误
    error = "error"


class ResourcePath(object):
    """
    path = ResourcePath("api.xxx")
    path.loaded()
    path.ignored()
    path.error()
    """

    def __init__(self, path):
        status = ResourceStatus.unloaded
        path_info = path.split(":")
        if len(path_info) > 1:
            rspath, status = path_info[:2]
        else:
            rspath = path_info[0]

        self.path = rspath.strip()
        self.status = status.strip()

    def __getattr__(self, item):
        status = getattr(ResourceStatus, item, None)
        if status:
            return status_setter(status)(lambda: status, self)

    def __repr__(self):
        return "{}: {}".format(self.path, self.status)


def status_setter(status):
    def setter(func, path):
        path.status = status
        return func

    return setter
