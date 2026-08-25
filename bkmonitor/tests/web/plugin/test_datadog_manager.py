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


import zipfile

from monitor_web.plugin.manager.datadog import DataDogPluginManager


class TestDatadogPlugin(object):
    def test_safe_extractall_skips_members_outside_destination(self, tmp_path, caplog):
        archive_path = tmp_path / "archive.zip"
        extract_dir = tmp_path / "nested" / "extract"
        outside_member = "../../tmp/x"
        outside_path = (extract_dir / outside_member).resolve()

        with zipfile.ZipFile(str(archive_path), "w") as zip_ref:
            zip_ref.writestr(outside_member, "outside")
            zip_ref.writestr("ok.txt", "ok")

        with zipfile.ZipFile(str(archive_path), "r") as zip_ref:
            DataDogPluginManager._safe_extractall(zip_ref, str(extract_dir))

        assert (extract_dir / "ok.txt").read_text() == "ok"
        assert not outside_path.exists()
        assert "Skipping zip member outside destination: ../../tmp/x" in caplog.text
