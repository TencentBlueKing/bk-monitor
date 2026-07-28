"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from unittest.mock import MagicMock, PropertyMock

import pytest
import fakeredis

from metadata.models.feature_flag import FeatureFlag, FeatureFlagConfig
from metadata.tests.conftest import MockHashConsul

# feature_flag 测试不需要数据库，只测试配置读写功能
# pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture(autouse=True)
def setup_env_vars(monkeypatch):
    """自动设置测试所需的环境变量"""
    monkeypatch.setenv("BK_PAAS_HOST", "http://localhost:8000")
    monkeypatch.setenv("APP_ID", "bk_monitor")
    monkeypatch.setenv("APP_TOKEN", "test_token")
    monkeypatch.setenv("BKPAAS_MAJOR_VERSION", "3")
    monkeypatch.setenv("USE_DYNAMIC_SETTINGS", "0")
    monkeypatch.setenv("BKAPP_DEPLOY_PLATFORM", "enterprise")
    monkeypatch.setenv("BK_MONITOR_APP_CODE", "bk_monitor")
    monkeypatch.setenv("BK_MONITOR_APP_SECRET", "test_secret")


class TestFeatureFlagConfig:
    """特性开关配置测试类"""

    @pytest.fixture
    def sample_feature_flags(self):
        """测试用的特性开关配置数据"""
        return {
            "must-vm-query": {
                "variations": {
                    "Default": False,
                    "true": True,
                    "false": False,
                },
                "targeting": [
                    {
                        "query": 'tableID in ["table_id_1", "table_id_2"]',
                        "percentage": {
                            "true": 100,
                            "false": 0,
                        },
                    }
                ],
                "defaultRule": {
                    "variation": "Default",
                },
            },
            "range-vm-query": {
                "variations": {
                    "Default": 0,
                    "true": 30000,
                },
                "targeting": [
                    {
                        "query": 'tableID in ["table_id_1", "table_id_3"]',
                        "percentage": {
                            "true": 100,
                        },
                    }
                ],
                "defaultRule": {
                    "variation": "Default",
                },
            },
        }

    @pytest.fixture
    def mock_consul(self, mocker):
        """Mock Consul 客户端"""
        mock_hash_consul = MockHashConsul()
        mocker.patch("metadata.models.feature_flag.consul_tools.HashConsul", return_value=mock_hash_consul)
        return mock_hash_consul

    @pytest.fixture
    def mock_redis(self, mocker):
        """Mock Redis 客户端"""
        mock_redis_client = fakeredis.FakeRedis(decode_responses=False)
        mock_redis_instance = MagicMock()
        mock_redis_instance.client = mock_redis_client
        mocker.patch("metadata.models.feature_flag.RedisTools", return_value=mock_redis_instance)
        from metadata.utils.redis_tools import RedisTools

        mocker.patch.object(RedisTools, "client", new_callable=PropertyMock, return_value=mock_redis_client)
        return mock_redis_client

    def test_refresh_consul_feature_flag_config(self, sample_feature_flags, mock_consul):
        """测试刷新特性开关配置到 Consul"""
        # 执行刷新操作
        FeatureFlagConfig.refresh_consul_feature_flag_config(sample_feature_flags)

        # 验证 Consul 中是否写入了配置（所有 flags 存储在一个 key 中）
        consul_path = FeatureFlagConfig.CONSUL_PREFIX_PATH
        index, consul_data = mock_consul.get(consul_path)

        # 验证配置已写入
        assert consul_data is not None
        assert "Value" in consul_data

        # 验证配置内容正确（应该包含所有 flags）
        stored_value = (
            json.loads(consul_data["Value"]) if isinstance(consul_data["Value"], str) else consul_data["Value"]
        )
        assert isinstance(stored_value, dict)
        assert len(stored_value) == len(sample_feature_flags)

        # 验证每个 flag 的配置都正确
        for flag_name, flag_config in sample_feature_flags.items():
            assert flag_name in stored_value
            assert stored_value[flag_name] == flag_config

    def test_refresh_redis_feature_flag_config(self, sample_feature_flags, mock_redis, mocker):
        """测试刷新特性开关配置到 Redis"""
        publish_spy = mocker.spy(mock_redis, "publish")

        # 执行刷新操作
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 验证 Redis 中是否写入了配置（所有 flags 存储在一个 key 中）
        redis_key = FeatureFlagConfig.REDIS_PREFIX_KEY
        stored_value_str = mock_redis.get(redis_key)

        # 验证配置已写入
        assert stored_value_str is not None

        # 验证配置内容正确（应该包含所有 flags）
        stored_value = json.loads(
            stored_value_str.decode("utf-8") if isinstance(stored_value_str, bytes) else stored_value_str
        )
        assert isinstance(stored_value, dict)
        assert len(stored_value) == len(sample_feature_flags)

        # 验证每个 flag 的配置都正确
        for flag_name, flag_config in sample_feature_flags.items():
            assert flag_name in stored_value
            assert stored_value[flag_name] == flag_config
        assert publish_spy.call_count == 1
        assert publish_spy.call_args.args[0] == FeatureFlagConfig.REDIS_CHANNEL

    def test_refresh_empty_redis_feature_flag_config_deletes_and_publishes(self, mock_redis, mocker):
        """清空配置时删除聚合 Key，并通知 UQ reload。"""
        mock_redis.set(FeatureFlagConfig.REDIS_PREFIX_KEY, "{}")
        publish_spy = mocker.spy(mock_redis, "publish")

        FeatureFlagConfig.refresh_redis_feature_flag_config({})

        assert mock_redis.get(FeatureFlagConfig.REDIS_PREFIX_KEY) is None
        assert publish_spy.call_count == 1
        assert publish_spy.call_args.args[0] == FeatureFlagConfig.REDIS_CHANNEL

    def test_force_refresh_empty_config_cleans_both_backends(self, mocker):
        """空数据库强刷也应让 Consul 和 Redis 收敛到空配置。"""
        mocker.patch("metadata.models.feature_flag.FeatureFlag.objects.filter", return_value=[])
        refresh_consul = mocker.patch.object(FeatureFlagConfig, "refresh_consul_feature_flag_config")
        refresh_redis = mocker.patch.object(FeatureFlagConfig, "refresh_redis_feature_flag_config")

        FeatureFlagConfig.force_refresh_feature_flag_config()

        refresh_consul.assert_called_once_with({})
        refresh_redis.assert_called_once_with({})

    def test_external_refresh_attempts_redis_when_consul_fails(self, mocker):
        """单个后端失败不能阻止另一个后端刷新。"""
        feature_flag = MagicMock()
        feature_flag.flag_name = "must-vm-query"
        feature_flag.to_config_dict.return_value = {"variations": {"Default": False}}
        mocker.patch("metadata.models.feature_flag.FeatureFlag.objects.filter", return_value=[feature_flag])
        mocker.patch.object(
            FeatureFlagConfig,
            "refresh_consul_feature_flag_config",
            side_effect=RuntimeError("consul unavailable"),
        )
        refresh_redis = mocker.patch.object(FeatureFlagConfig, "refresh_redis_feature_flag_config")

        FeatureFlag._refresh_external_config("must-vm-query", "saved")

        refresh_redis.assert_called_once_with(
            {"must-vm-query": {"variations": {"Default": False}}}
        )

    def test_partial_save_persists_updater_and_defers_refresh(self, mocker):
        """部分更新必须持久化 updater，并在事务提交后刷新。"""
        model_save = mocker.patch("django.db.models.Model.save")
        on_commit = mocker.patch("metadata.models.feature_flag.transaction.on_commit")
        feature_flag = FeatureFlag(flag_name="must-vm-query", config={})

        feature_flag.save(operator="admin", update_fields={"config"})

        assert feature_flag.updater == "admin"
        assert model_save.call_args.kwargs["update_fields"] == {"config", "updater"}
        on_commit.assert_called_once()

    def test_get_consul_feature_flag_config(self, sample_feature_flags, mock_consul):
        """测试从 Consul 读取特性开关配置"""
        # 先写入配置
        FeatureFlagConfig.refresh_consul_feature_flag_config(sample_feature_flags)

        # 读取配置
        config = FeatureFlagConfig.get_consul_feature_flag_config("must-vm-query")

        # 验证配置内容
        assert config is not None
        assert config == sample_feature_flags["must-vm-query"]

        # 测试读取不存在的配置
        non_existent = FeatureFlagConfig.get_consul_feature_flag_config("non-existent-flag")
        assert non_existent is None

    def test_get_redis_feature_flag_config(self, sample_feature_flags, mock_redis):
        """测试从 Redis 读取特性开关配置"""
        # 先写入配置
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 读取配置
        config = FeatureFlagConfig.get_redis_feature_flag_config("must-vm-query")

        # 验证配置内容
        assert config is not None
        assert config == sample_feature_flags["must-vm-query"]

        # 测试读取不存在的配置
        non_existent = FeatureFlagConfig.get_redis_feature_flag_config("non-existent-flag")
        assert non_existent is None

    def test_get_feature_flag_config_prefer_redis(self, sample_feature_flags, mock_redis, mock_consul):
        """测试获取特性开关配置，优先从 Redis 读取"""
        # 只写入 Redis
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 读取配置（优先 Redis）
        config = FeatureFlagConfig.get_feature_flag_config("must-vm-query", prefer_redis=True)

        # 验证从 Redis 读取
        assert config is not None
        assert config == sample_feature_flags["must-vm-query"]

    def test_get_feature_flag_config_prefer_consul(self, sample_feature_flags, mock_redis, mock_consul):
        """测试获取特性开关配置，优先从 Consul 读取"""
        # 只写入 Consul
        FeatureFlagConfig.refresh_consul_feature_flag_config(sample_feature_flags)

        # 读取配置（优先 Consul）
        config = FeatureFlagConfig.get_feature_flag_config("must-vm-query", prefer_redis=False)

        # 验证从 Consul 读取
        assert config is not None
        assert config == sample_feature_flags["must-vm-query"]

    def test_get_feature_flag_config_fallback(self, sample_feature_flags, mock_redis, mock_consul):
        """测试获取特性开关配置的回退机制"""
        # 只写入 Consul，不写入 Redis
        FeatureFlagConfig.refresh_consul_feature_flag_config(sample_feature_flags)

        # 优先从 Redis 读取（Redis 中没有，应该回退到 Consul）
        config = FeatureFlagConfig.get_feature_flag_config("must-vm-query", prefer_redis=True)

        # 验证从 Consul 读取（回退）
        assert config is not None
        assert config == sample_feature_flags["must-vm-query"]

    def test_get_feature_flag_value_with_table_id_match(self, sample_feature_flags, mock_redis):
        """测试根据 table_id 获取特性开关值，匹配 targeting 规则"""
        # 写入配置
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 测试匹配的 table_id
        value = FeatureFlagConfig.get_feature_flag_value("must-vm-query", table_id="table_id_1", prefer_redis=True)

        # 验证返回正确的值（percentage["true"] = 100，应该返回 True）
        assert value is True

        # 测试另一个匹配的 table_id
        value2 = FeatureFlagConfig.get_feature_flag_value("must-vm-query", table_id="table_id_2", prefer_redis=True)
        assert value2 is True

    def test_get_feature_flag_value_with_table_id_no_match(self, sample_feature_flags, mock_redis):
        """测试根据 table_id 获取特性开关值，不匹配 targeting 规则"""
        # 写入配置
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 测试不匹配的 table_id
        value = FeatureFlagConfig.get_feature_flag_value("must-vm-query", table_id="table_id_999", prefer_redis=True)

        # 验证返回默认值（Default 对应的 False）
        assert value is False

    def test_get_feature_flag_value_without_table_id(self, sample_feature_flags, mock_redis):
        """测试获取特性开关值，不提供 table_id"""
        # 写入配置
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 不提供 table_id，应该返回默认值
        value = FeatureFlagConfig.get_feature_flag_value("must-vm-query", prefer_redis=True)

        # 验证返回默认值
        assert value is False  # Default 对应的值

    def test_get_feature_flag_value_numeric_variation(self, sample_feature_flags, mock_redis):
        """测试获取数值类型的特性开关值"""
        # 写入配置
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 测试 range-vm-query（数值类型）
        value = FeatureFlagConfig.get_feature_flag_value("range-vm-query", table_id="table_id_1", prefer_redis=True)

        # 验证返回正确的值（percentage["true"] = 100，应该返回 30000）
        assert value == 30000

        # 测试不匹配的情况，应该返回默认值 0
        value_default = FeatureFlagConfig.get_feature_flag_value(
            "range-vm-query", table_id="table_id_999", prefer_redis=True
        )
        assert value_default == 0

    def test_get_feature_flag_value_config_not_found(self, mock_redis):
        """测试获取不存在的特性开关配置"""
        # 不写入任何配置

        # 尝试读取不存在的配置
        value = FeatureFlagConfig.get_feature_flag_value("non-existent-flag", prefer_redis=True)

        # 验证返回 None
        assert value is None

    def test_get_feature_flag_value_with_percentage_false(self, mock_redis):
        """测试 percentage["false"] = 100 的情况"""
        feature_flags = {
            "test-flag": {
                "variations": {
                    "Default": None,
                    "true": True,
                    "false": False,
                },
                "targeting": [
                    {
                        "query": 'tableID in ["table_id_1"]',
                        "percentage": {
                            "true": 0,
                            "false": 100,
                        },
                    }
                ],
                "defaultRule": {
                    "variation": "Default",
                },
            }
        }

        # 写入配置
        FeatureFlagConfig.refresh_redis_feature_flag_config(feature_flags)

        # 测试匹配的 table_id
        value = FeatureFlagConfig.get_feature_flag_value("test-flag", table_id="table_id_1", prefer_redis=True)

        # 验证返回 False（percentage["false"] = 100）
        assert value is False

    def test_get_all_consul_feature_flag_config(self, sample_feature_flags, mock_consul):
        """测试从 Consul 读取所有特性开关配置"""
        # 先写入配置
        FeatureFlagConfig.refresh_consul_feature_flag_config(sample_feature_flags)

        # 读取所有配置
        all_configs = FeatureFlagConfig.get_all_consul_feature_flag_config()

        # 验证返回了所有配置
        assert all_configs is not None
        assert isinstance(all_configs, dict)
        assert len(all_configs) == len(sample_feature_flags)
        assert "must-vm-query" in all_configs
        assert "range-vm-query" in all_configs

    def test_get_all_redis_feature_flag_config(self, sample_feature_flags, mock_redis):
        """测试从 Redis 读取所有特性开关配置"""
        # 先写入配置
        FeatureFlagConfig.refresh_redis_feature_flag_config(sample_feature_flags)

        # 读取所有配置
        all_configs = FeatureFlagConfig.get_all_redis_feature_flag_config()

        # 验证返回了所有配置
        assert all_configs is not None
        assert isinstance(all_configs, dict)
        assert len(all_configs) == len(sample_feature_flags)
        assert "must-vm-query" in all_configs
        assert "range-vm-query" in all_configs
