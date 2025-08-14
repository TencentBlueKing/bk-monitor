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


import hashlib
import os
import shutil
import tarfile

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext as _

from bkmonitor.utils.request import get_request_tenant_id
from monitor_web.models.file import UploadedFileInfo
from monitor_web.models.plugin import CollectorPluginMeta


class BaseFileManager(object):
    TYPE = ""

    def __init__(self, file):
        self._file_content = None
        if isinstance(file, UploadedFileInfo):
            _file = file
        else:
            try:
                file_id = int(file)
                _file = UploadedFileInfo.objects.get(id=file_id)
            except UploadedFileInfo.DoesNotExist:
                raise FileManagerException(_("不存在指定文件"))

        if _file.file_data.name.startswith(self.TYPE):
            self.file_obj = _file
            self.file_url = _file.file_data.url
        else:
            raise FileManagerException(_("%s模块下不存在指定文件") % self.TYPE)

    @classmethod
    def _get_or_create(cls, original_filename, actual_filename, file_md5, relative_path, is_dir=False):
        # 判断是否已存在该文件
        file_obj = UploadedFileInfo.objects.filter(
            file_md5=file_md5, actual_filename=actual_filename, relative_path__startswith=cls.TYPE
        ).first()
        if file_obj:
            return file_obj, True

        file_obj = UploadedFileInfo.objects.create(
            actual_filename=actual_filename,
            original_filename=original_filename,
            relative_path=relative_path,
            file_md5=file_md5,
            is_dir=is_dir,
        )
        return file_obj, False

    @classmethod
    def save_dir(cls, dir_path, dir_name):
        """
        保存目录
        先将目录压缩成tgz，再进行
        :param dir_path:
        :param dir_name:
        :return:
        """
        # file_tree = os.walk(dir_path)
        tar_name = dir_name + ".zip"
        tar_path = os.path.join(os.path.dirname(dir_path), tar_name)

        shutil.make_archive(os.path.join(os.path.dirname(dir_path), dir_name), "zip", dir_path)

        with open(tar_path, "rb") as f:
            file_content = f.read()

        return cls.save_file(file_data=file_content, file_name=tar_name, is_dir=True)

    @classmethod
    def save_file(cls, file_data, file_name=None, is_dir=False, *args, **kwargs):
        """
        保存文件
        :param file_name:
        :param file_data:
        :param is_dir: 是否为目录
        :return:
        """
        relative_path = cls._get_relative_path(*args, **kwargs)
        if isinstance(file_data, UploadedFile):
            if not file_name:
                file_name = file_data.name

            file_content = file_data.read()
            file_md5 = hashlib.md5(file_content).hexdigest()
            file_obj, is_created = cls._get_or_create(
                original_filename=file_data.name,
                actual_filename=file_name,
                file_md5=file_md5,
                relative_path=relative_path,
                is_dir=is_dir,
            )
            fd = file_data
        else:
            assert file_name
            file_md5 = hashlib.md5(file_data).hexdigest()
            fd = ContentFile(file_data)
            file_obj, is_created = cls._get_or_create(
                original_filename=file_name,
                actual_filename=file_name,
                file_md5=file_md5,
                relative_path=relative_path,
                is_dir=is_dir,
            )

        file_obj.file_data.save(file_name, fd)
        return cls(file_obj)

    @classmethod
    def _get_relative_path(cls, *args, **kwargs):
        """
        实际保存的相对路径
        :return:
        """
        return ""

    def read_file(self):
        """
        读取文件内容
        :return:
        """
        if self.file_obj and not self._file_content:
            self._file_content = self.file_obj.file_data.read()

        return self._file_content

    def verify_md5(self, md5):
        return self.file_obj.file_md5 == md5

    @staticmethod
    def clean_dir(path):
        if path and os.path.exists(path):
            shutil.rmtree(path)


class PluginFileManager(BaseFileManager):
    TYPE = "plugin"

    @classmethod
    def _get_relative_path(cls, plugin_id=None):
        if plugin_id:
            return os.path.join(cls.TYPE, plugin_id)

        return os.path.join(cls.TYPE, "_tmp")

    @classmethod
    def save_file(cls, file_data, file_name=None, is_dir=False, *args, **kwargs):
        plugin_id = kwargs.get("plugin_id")
        if plugin_id:
            try:
                plugin_meta = CollectorPluginMeta.objects.get(bk_tenant_id=get_request_tenant_id(), plugin_id=plugin_id)
                return super(PluginFileManager, cls).save_file(
                    file_data=file_data, file_name=file_name, is_dir=False, plugin_id=plugin_meta.plugin_id
                )
            except CollectorPluginMeta.DoesNotExist:
                raise FileManagerException(_("非法的plugin_id"))

        return super(PluginFileManager, cls).save_file(file_data, file_name, False)

    @classmethod
    def save_plugin(cls, file_data, file_path):
        with open(file_path, "wb+") as fp:
            for chunk in file_data.chunks():
                fp.write(chunk)

    @classmethod
    def extract_file(cls, file_data, file_path):
        with tarfile.open(fileobj=file_data, mode="r:gz") as tar:
            tar.extractall(file_path, filter='data')
        return file_path

    @classmethod
    def valid_file(cls, file_data, os_type):
        pass


class ExportImportManager(BaseFileManager):
    TYPE = "export_import"

    @classmethod
    def _get_relative_path(cls):
        import_path = os.path.join(cls.TYPE, "import")
        return import_path


class FileManagerException(Exception):
    def __init__(self, error=None):
        if error is None:
            error = _("文件操作异常")
        super(FileManagerException, self).__init__(error)


def walk(storage, top="/", topdown=False, onerror=None):
    """An implementation of os.walk() which uses the Django storage for
    listing directories."""
    try:
        dirs, nondirs = storage.listdir(top)
    except os.error as err:
        if onerror is not None:
            onerror(err)
        return

    if topdown:
        yield top, dirs, nondirs
    for name in dirs:
        new_path = os.path.join(top, name)
        for x in walk(storage, new_path):
            yield x
    if not topdown:
        yield top, dirs, nondirs
