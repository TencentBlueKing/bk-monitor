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
import base64
import os
import tarfile
from uuid import uuid4

import yaml
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.translation import gettext as _

from core.errors.event_plugin import PluginParseError


class PackageHandler:
    class FileName:
        PLUGIN_INFO = "plugin.yaml"
        DESCRIPTION = "description.md"
        TUTORIAL = "tutorial.md"
        LOGO = "logo.png"
        ALERT = "alert.yaml"

    def __init__(self, package_dir: str):
        self.package_dir = package_dir

    def get_package_dir(self):
        return self.package_dir

    def read_file(self, filename, ignore_error=False):
        try:
            with default_storage.open(os.path.join(self.get_media_root(), self.package_dir, filename)) as fd:
                file_content = fd.read()
        except IOError:
            if ignore_error:
                return None
            else:
                raise PluginParseError({"msg": _("%s 文件读取失败") % filename})

        try:
            file_content = file_content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        return file_content

    def parse(self) -> dict:
        """
        解析插件包，并返回创建插件所需的参数
        """
        plugin_info = self._parse_yaml_file(self.FileName.PLUGIN_INFO)

        extra_info = {
            "alert_config": self._parse_yaml_file(self.FileName.ALERT, ignore_error=True),
            "logo": self._parse_logo(),
            "description": self._parse_text_file(self.FileName.DESCRIPTION, ignore_error=True),
            "tutorial": self._parse_text_file(self.FileName.TUTORIAL, ignore_error=True),
        }

        for key, value in extra_info.items():
            if value:
                plugin_info[key] = value
        return plugin_info

    def _parse_yaml_file(self, filename, ignore_error=False):
        content = self.read_file(filename, ignore_error)
        try:
            return yaml.load(content, Loader=yaml.FullLoader)
        except Exception as e:
            if ignore_error:
                return None
            else:
                raise PluginParseError({"msg": _("{} 解析失败: {}").format(filename, e)})

    def _parse_text_file(self, filename, ignore_error=False):
        return self.read_file(filename, ignore_error)

    def _parse_logo(self) -> str:
        try:
            content = self.read_file(self.FileName.LOGO, ignore_error=True)
        except BaseException:
            content = None
        return base64.b64encode(content).decode("utf-8") if content else None

    @classmethod
    def get_media_root(cls):
        return "event_plugin"

    @classmethod
    def from_tar_file(cls, tar_file):
        """
        从压缩包提取出来
        """
        package_dir = str(uuid4())
        with tarfile.open(fileobj=tar_file, mode="r:gz") as tar:
            _fileobj = tar.fileobj
            # 这里不能使用getmenbers，如果使用就无法获取到子目录下的文件，因此需要使用迭代器，利用self.next依次获取文件
            for tarinfo in tar:
                if tarinfo.isdir():
                    continue
                _fileobj.seek(tarinfo.offset_data)
                try:
                    default_storage.save(
                        os.path.join(cls.get_media_root(), package_dir, tarinfo.name),
                        ContentFile(_fileobj.read(tarinfo.size)),
                    )
                except Exception as e:
                    raise PluginParseError({"msg": _("插件包保存失败: %s") % e})
            return cls(package_dir=package_dir)
