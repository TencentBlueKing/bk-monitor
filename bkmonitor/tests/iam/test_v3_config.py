"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ==============================================================================
# V3Options / V3Credentials / V3SystemInfo 配置解析单元测试
#
# 覆盖：
#   1. 正常 dict 解析
#   2. 必填字段缺失 → ValueError
#   3. 类型错误
#   4. frozen dataclass 不可变
#   5. extra 字段收纳
# ==============================================================================

import pytest

from bkmonitor.iam.iam_v3.config import V3Credentials, V3Options, V3SystemInfo


class TestV3Credentials:
    """V3Credentials：凭据配置 from_dict。"""

    def test_from_dict_ok(self):
        raw = {"app_code": "my_app", "app_secret": "my_secret"}
        c = V3Credentials.from_dict(raw)
        assert c.app_code == "my_app"
        assert c.app_secret == "my_secret"

    def test_from_dict_missing_app_code(self):
        with pytest.raises(ValueError):
            V3Credentials.from_dict({"app_secret": "x"})

    def test_from_dict_missing_app_secret(self):
        with pytest.raises(ValueError):
            V3Credentials.from_dict({"app_code": "x"})

    def test_frozen(self):
        c = V3Credentials(app_code="a", app_secret="b")
        with pytest.raises(Exception):
            c.app_code = "new"  # type: ignore[misc]


class TestV3SystemInfo:
    """V3SystemInfo：系统信息配置 from_dict。"""

    def test_from_dict_minimal(self):
        raw = {"id": "bk_monitorv3", "name": "监控平台"}
        s = V3SystemInfo.from_dict(raw)
        assert s.id == "bk_monitorv3"
        assert s.name == "监控平台"
        assert s.description == ""
        assert s.managers == ()
        assert s.clients == ()

    def test_from_dict_full(self):
        raw = {
            "id": "bk_monitorv3",
            "name": "监控平台",
            "description": "蓝鲸监控 V3",
            "managers": ["admin"],
            "clients": ["bk_monitor", "bk_log"],
        }
        s = V3SystemInfo.from_dict(raw)
        assert s.description == "蓝鲸监控 V3"
        assert s.managers == ("admin",)
        assert s.clients == ("bk_monitor", "bk_log")

    def test_missing_id(self):
        with pytest.raises(ValueError):
            V3SystemInfo.from_dict({"name": "x"})

    def test_missing_name(self):
        with pytest.raises(ValueError):
            V3SystemInfo.from_dict({"id": "x"})

    def test_frozen(self):
        s = V3SystemInfo(id="x", name="y")
        with pytest.raises(Exception):
            s.id = "new"  # type: ignore[misc]


def _valid_options_dict() -> dict:
    return {
        "base_url": "https://iam.example.com",
        "credentials": {"app_code": "test_app", "app_secret": "test_secret"},
        "system": {"id": "bk_monitorv3", "name": "监控平台"},
        "bk_tenant_id": "default",
    }


class TestV3Options:
    """V3Options：Provider 完整配置 from_dict。"""

    def test_from_dict_minimal(self):
        raw = _valid_options_dict()
        opts = V3Options.from_dict(raw)
        assert opts.base_url == "https://iam.example.com"
        assert opts.credentials.app_code == "test_app"
        assert opts.system.id == "bk_monitorv3"
        # 默认值
        assert opts.bk_tenant_id == "default"
        assert opts.timeout == 30
        assert opts.chunk_size == 20
        assert opts.max_workers == 1
        assert opts.extra == {}

    def test_defaults(self):
        raw = {
            "base_url": "https://iam.example.com",
            "credentials": {"app_code": "a", "app_secret": "s"},
            "system": {"id": "x", "name": "y"},
        }
        opts = V3Options.from_dict(raw)
        assert opts.bk_tenant_id == ""
        assert opts.timeout == 30
        assert opts.chunk_size == 20
        assert opts.max_workers == 1

    def test_overrides(self):
        raw = _valid_options_dict()
        raw.update({"timeout": 60, "chunk_size": 10, "max_workers": 4})
        opts = V3Options.from_dict(raw)
        assert opts.timeout == 60
        assert opts.chunk_size == 10
        assert opts.max_workers == 4

    def test_missing_base_url(self):
        raw = _valid_options_dict()
        del raw["base_url"]
        with pytest.raises(ValueError):
            V3Options.from_dict(raw)

    def test_missing_credentials(self):
        raw = _valid_options_dict()
        del raw["credentials"]
        with pytest.raises(ValueError):
            V3Options.from_dict(raw)

    def test_missing_system(self):
        raw = _valid_options_dict()
        del raw["system"]
        with pytest.raises(ValueError):
            V3Options.from_dict(raw)

    def test_credentials_not_dict(self):
        raw = _valid_options_dict()
        raw["credentials"] = "not-a-dict"
        with pytest.raises(ValueError):
            V3Options.from_dict(raw)

    def test_system_not_dict(self):
        raw = _valid_options_dict()
        raw["system"] = "not-a-dict"
        with pytest.raises(ValueError):
            V3Options.from_dict(raw)

    def test_extra_fields_collected(self):
        raw = _valid_options_dict()
        raw["unknown_field"] = "surprise"
        raw["another_unknown"] = 42
        opts = V3Options.from_dict(raw)
        assert opts.extra == {"unknown_field": "surprise", "another_unknown": 42}

    def test_frozen(self):
        opts = V3Options.from_dict(_valid_options_dict())
        with pytest.raises(Exception):
            opts.base_url = "new"  # type: ignore[misc]
