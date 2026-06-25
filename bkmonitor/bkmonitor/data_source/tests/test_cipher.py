"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bkmonitor.utils.cipher import get_bk_data_token_aes_key


@pytest.mark.parametrize(
    "settings_values,expected_key",
    [
        (
            {
                "CUSTOM_REPORT_AES_KEY": "custom-report-key",
                "SPECIFY_AES_KEY": "specify-key",
                "AES_X_KEY_FIELD": "SECRET_KEY",
                "SECRET_KEY": "secret-key",
            },
            "custom-report-key",
        ),
        (
            {
                "CUSTOM_REPORT_AES_KEY": "",
                "SPECIFY_AES_KEY": "specify-key",
                "AES_X_KEY_FIELD": "SECRET_KEY",
                "SECRET_KEY": "secret-key",
            },
            "specify-key",
        ),
        (
            {
                "CUSTOM_REPORT_AES_KEY": "",
                "SPECIFY_AES_KEY": "",
                "AES_X_KEY_FIELD": "SAAS_SECRET_KEY",
                "SAAS_SECRET_KEY": "saas-secret-key",
            },
            "saas-secret-key",
        ),
    ],
)
def test_get_bk_data_token_aes_key_priority(settings, settings_values, expected_key):
    for key, value in settings_values.items():
        setattr(settings, key, value)

    assert get_bk_data_token_aes_key() == expected_key


def test_get_bk_data_token_aes_key_ignores_prefixed_env(monkeypatch, settings):
    monkeypatch.setenv("BKAPP_CUSTOM_REPORT_AES_KEY", "bkapp-custom-report-key")
    monkeypatch.setenv("BK_CUSTOM_REPORT_AES_KEY", "bk-custom-report-key")
    settings.CUSTOM_REPORT_AES_KEY = ""
    settings.SPECIFY_AES_KEY = "specify-key"
    settings.AES_X_KEY_FIELD = "SECRET_KEY"
    settings.SECRET_KEY = "secret-key"

    assert get_bk_data_token_aes_key() == "specify-key"
