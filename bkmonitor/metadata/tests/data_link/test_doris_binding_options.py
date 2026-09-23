"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pydantic
import pytest

from metadata.models.data_link.data_link_configs import DorisStorageBindingConfig
from metadata.models.result_table import CustomFormatV4DataLinkOption, LogV4DataLinkOption


@pytest.fixture
def enable_db_access():
    """覆盖父级自动启用数据库的 fixture；配置校验和渲染无需访问数据库。"""


@pytest.fixture(params=[False, True], ids=["single_tenant", "multi_tenant"])
def doris_binding(request, settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = request.param
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    return DorisStorageBindingConfig(name="log_binding", namespace="bklog", bk_biz_id=111, bk_tenant_id="system")


@pytest.mark.parametrize(
    "config_model",
    [LogV4DataLinkOption.DorisStorageConfig, CustomFormatV4DataLinkOption.DorisStorageConfig],
    ids=["log", "custom_format"],
)
@pytest.mark.parametrize(
    "tokenizer_option",
    [
        pytest.param({}, id="omitted"),
        pytest.param({"tokenizers": None}, id="null"),
        pytest.param({"tokenizers": {}}, id="empty"),
        pytest.param({"tokenizers": {"log": "._=:,"}}, id="custom"),
        pytest.param({"tokenizers": {"log": '"\\\n\t中文', "message": ""}}, id="special_characters"),
    ],
)
def test_doris_tokenizers_from_option_to_binding(doris_binding, config_model, tokenizer_option, settings):
    field_config_group = {"bloomfilter": ["ip"], "search_en": ["log"], "search_zh": ["message"]}
    option = config_model(storage_keys=[], field_config_group=field_config_group, **tokenizer_option)
    content = doris_binding.compose_config(
        storage_cluster_name="doris-default",
        expires="3d",
        rt_name="log_rt",
        **option.model_dump(),
    )

    storage_config = content["spec"]["storage_config"]
    if tokenizer_option.get("tokenizers") is None:
        assert "tokenizers" not in storage_config
    else:
        assert storage_config["tokenizers"] == tokenizer_option["tokenizers"]
    assert storage_config["field_config_group"] == field_config_group
    assert content["spec"]["data"]["name"] == "log_rt"
    for ref in (content["metadata"], content["spec"]["data"], content["spec"]["storage"]):
        if settings.ENABLE_MULTI_TENANT_MODE:
            assert ref["tenant"] == "system"
        else:
            assert "tenant" not in ref


@pytest.mark.parametrize(
    "config_model",
    [LogV4DataLinkOption.DorisStorageConfig, CustomFormatV4DataLinkOption.DorisStorageConfig],
    ids=["log", "custom_format"],
)
@pytest.mark.parametrize("tokenizers", ["._=:,", {"log": [".", "_"]}, {"log": 1}])
def test_doris_tokenizers_reject_invalid_types(config_model, tokenizers):
    with pytest.raises(pydantic.ValidationError, match="tokenizers"):
        config_model(storage_keys=[], tokenizers=tokenizers)
