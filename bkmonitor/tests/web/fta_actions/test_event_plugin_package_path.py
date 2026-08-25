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
import io
import tarfile
from unittest import mock

from django.core.exceptions import SuspiciousFileOperation

from fta_web.event_plugin.handler import PackageHandler


class RecordingStorage(object):
    def __init__(self, raise_on_dotdot=False):
        self.saved = []
        self.raise_on_dotdot = raise_on_dotdot

    def save(self, name, content):
        if self.raise_on_dotdot and ".." in name.replace("\\", "/"):
            raise SuspiciousFileOperation(name)
        self.saved.append(name)
        return name


def _build_tar(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content, typeflag in members:
            info = tarfile.TarInfo(name=name)
            payload = b""
            if content is not None:
                payload = content.encode("utf-8") if not isinstance(content, bytes) else content
                info.size = len(payload)
            if typeflag is not None:
                info.type = typeflag
            tar.addfile(info, io.BytesIO(payload) if info.isreg() else None)
    buf.seek(0)
    return buf


class TestPackageHandlerExtractPath(object):
    def test_skips_parent_dir_and_saves_legal_file(self):
        storage = RecordingStorage()
        tar_file = _build_tar(
            [
                ("ok.txt", "ok", tarfile.REGTYPE),
                ("ok/../../sibling", "escaped", tarfile.REGTYPE),
            ]
        )
        with mock.patch("fta_web.event_plugin.handler.default_storage", storage):
            handler = PackageHandler.from_tar_file(tar_file)
        assert any(name.endswith("ok.txt") for name in storage.saved)
        assert all("sibling" not in name for name in storage.saved)
        assert handler.package_dir
        assert all(handler.package_dir in name for name in storage.saved)

    def test_skips_absolute_path(self):
        storage = RecordingStorage()
        tar_file = _build_tar([("/tmp/outside.txt", "outside", tarfile.REGTYPE), ("plugin.yaml", "n: 1", tarfile.REGTYPE)])
        with mock.patch("fta_web.event_plugin.handler.default_storage", storage):
            PackageHandler.from_tar_file(tar_file)
        assert any(name.endswith("plugin.yaml") for name in storage.saved)
        assert all("outside.txt" not in name for name in storage.saved)

    def test_saves_legal_subdirectory(self):
        storage = RecordingStorage()
        tar_file = _build_tar([("subdir/plugin.yaml", "name: demo", tarfile.REGTYPE)])
        with mock.patch("fta_web.event_plugin.handler.default_storage", storage):
            handler = PackageHandler.from_tar_file(tar_file)
        assert storage.saved == ["event_plugin/%s/subdir/plugin.yaml" % handler.package_dir]

    def test_skips_symlink_and_device(self):
        storage = RecordingStorage()
        tar_file = _build_tar(
            [
                ("link", None, tarfile.SYMTYPE),
                ("dev", None, tarfile.CHRTYPE),
                ("ok.txt", "ok", tarfile.REGTYPE),
            ]
        )
        with mock.patch("fta_web.event_plugin.handler.default_storage", storage):
            PackageHandler.from_tar_file(tar_file)
        assert len(storage.saved) == 1
        assert storage.saved[0].endswith("ok.txt")

    def test_filesystem_backend_never_receives_dotdot_key(self):
        storage = RecordingStorage(raise_on_dotdot=True)
        tar_file = _build_tar(
            [
                ("ok.txt", "ok", tarfile.REGTYPE),
                ("../escape.txt", "escaped", tarfile.REGTYPE),
            ]
        )
        with mock.patch("fta_web.event_plugin.handler.default_storage", storage):
            PackageHandler.from_tar_file(tar_file)
        assert any(name.endswith("ok.txt") for name in storage.saved)
        assert all("escape.txt" not in name and ".." not in name for name in storage.saved)

    def test_bkrepo_like_backend_cannot_leave_package_prefix(self):
        storage = RecordingStorage()
        tar_file = _build_tar(
            [
                ("ok/../../sibling", "escaped", tarfile.REGTYPE),
                ("nested/file.txt", "ok", tarfile.REGTYPE),
            ]
        )
        with mock.patch("fta_web.event_plugin.handler.default_storage", storage):
            handler = PackageHandler.from_tar_file(tar_file)
        assert storage.saved == ["event_plugin/%s/nested/file.txt" % handler.package_dir]
        assert all(name.startswith("event_plugin/%s/" % handler.package_dir) for name in storage.saved)
