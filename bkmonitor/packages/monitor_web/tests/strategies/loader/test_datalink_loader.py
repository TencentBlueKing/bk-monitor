import copy

import pytest

from bkmonitor.models import (
    AlertAssignGroup,
    AlertAssignRule,
    DutyArrange,
    StrategyModel,
    UserGroup,
)
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.models import CollectConfigMeta, CollectorPluginMeta
from monitor_web.plugin.constant import PluginType
from monitor_web.strategies.default_settings.datalink.v1 import (
    DEFAULT_DATALINK_STRATEGIES,
    GATHER_UP_DATA_LABEL,
)
from monitor_web.strategies.loader.datalink_loader import (
    DatalinkDefaultAlarmStrategyLoader,
)

pytestmark = pytest.mark.django_db(databases=["default", "monitor_api"])


BK_BIZ_ID = 2
USER_ID = "test_user"
ANOTHER_USER_ID = "another_test_user"


@pytest.fixture
def setup_and_run_loader():
    """loader 工厂，并运行 run 方法。"""

    def _loader_runner(collect_config_id=1, user_id=USER_ID, config_name="default_config"):
        plugin = CollectorPluginMeta(bk_biz_id=BK_BIZ_ID, plugin_type=PluginType.SCRIPT)
        collect_config = CollectConfigMeta(
            id=collect_config_id, bk_biz_id=BK_BIZ_ID, name=config_name, plugin_id=plugin.plugin_id
        )

        loader = DatalinkDefaultAlarmStrategyLoader(collect_config=collect_config, user_id=user_id)
        loader.run()

        return loader

    return _loader_runner


class TestDatalinkStrategyLoader:
    def test_run(self, setup_and_run_loader):
        """测试简单创建链路健康策略的情况。"""
        setup_and_run_loader()

        # 创建了分派规则、分派组、策略、用户组
        assert AlertAssignRule.objects.count() == 2
        assert AlertAssignGroup.objects.count() == 1
        assert StrategyModel.objects.count() == 2
        assert UserGroup.objects.count() == 1

        # 用户存在于告警组中
        assert DutyArrange.objects.filter(users__contains={"id": USER_ID}).exists()

    def test_delete_all(self, setup_and_run_loader):
        """测试全部采集配置删除后链路健康策略同步删除的情况。"""
        loader = setup_and_run_loader()
        loader.delete(remove_user_from_group=True)

        # 分派规则全部删除
        assert not AlertAssignRule.objects.exists()

    def test_delete_with_not_keep_user(self, setup_and_run_loader):
        """测试只删除部分采集配置（不同用户创建）的情况。"""
        setup_and_run_loader()
        loader = setup_and_run_loader(collect_config_id=2, user_id=ANOTHER_USER_ID)
        loader.delete(remove_user_from_group=True)

        assert AlertAssignRule.objects.count() == 2
        assert not DutyArrange.objects.filter(users__contains={"id": ANOTHER_USER_ID}).exists()

    def test_delete_with_keep_user(self, setup_and_run_loader):
        """测试只删除部分采集配置（同一用户创建）的情况。"""
        setup_and_run_loader()
        loader = setup_and_run_loader(collect_config_id=2)
        loader.delete()

        assert AlertAssignRule.objects.count() == 2
        assert DutyArrange.objects.filter(users__contains={"id": USER_ID}).exists()


class TestDatalinkStrategyMultiTenantAdaptation:
    """gather_up 采集状态默认策略的多租户查询配置适配。"""

    @staticmethod
    def _build_strategy() -> dict:
        strategy = copy.deepcopy(DEFAULT_DATALINK_STRATEGIES[0])
        strategy.pop("_name", None)
        return strategy

    @staticmethod
    def _build_loader(bk_tenant_id: str = "tenant", bk_biz_id: int = BK_BIZ_ID) -> DatalinkDefaultAlarmStrategyLoader:
        collect_config = CollectConfigMeta(
            id=1,
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            name="default_config",
            plugin_id="test_plugin",
        )
        return DatalinkDefaultAlarmStrategyLoader(collect_config=collect_config, user_id=USER_ID)

    def test_adapt_query_config_multi_tenant(self, settings):
        """多租户按业务建链时改用分业务自定义时序结果表。"""
        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.SPACE_BUILTIN_DATA_LINK_MODE = ""
        strategy = self._build_strategy()
        loader = self._build_loader()

        loader._adapt_query_config_for_multi_tenant(strategy)

        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                assert query_config["data_source_label"] == DataSourceLabel.CUSTOM
                assert query_config["data_type_label"] == DataTypeLabel.TIME_SERIES
                assert query_config["result_table_id"] == "tenant_2_bkmonitorbeat_gather_up.__default__"
                assert query_config["data_label"] == GATHER_UP_DATA_LABEL

    def test_adapt_query_config_multi_tenant_mode_uses_neutral_table(self, settings):
        """多租户按租户建链时引用不带业务/租户前缀的中立 gather_up 结果表。"""
        settings.ENABLE_MULTI_TENANT_MODE = True
        settings.SPACE_BUILTIN_DATA_LINK_MODE = "tenant"
        strategy = self._build_strategy()
        loader = self._build_loader(bk_tenant_id="tenant", bk_biz_id=BK_BIZ_ID)

        loader._adapt_query_config_for_multi_tenant(strategy)

        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                assert query_config["data_source_label"] == DataSourceLabel.CUSTOM
                assert query_config["data_type_label"] == DataTypeLabel.TIME_SERIES
                assert query_config["result_table_id"] == "bkmonitorbeat_gather_up.__default__"
                assert query_config["data_label"] == GATHER_UP_DATA_LABEL

    def test_adapt_query_config_single_tenant(self, settings):
        """单租户保持原全局结果表不变。"""
        settings.ENABLE_MULTI_TENANT_MODE = False
        strategy = self._build_strategy()
        loader = self._build_loader()

        loader._adapt_query_config_for_multi_tenant(strategy)

        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                assert query_config["result_table_id"] == "bkmonitorbeat_gather_up.__default__"
                assert "data_label" not in query_config
