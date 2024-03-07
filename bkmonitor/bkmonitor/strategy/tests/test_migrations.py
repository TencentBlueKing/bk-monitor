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
from django.apps import apps as django_apps
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import StateApps
from django.test import TransactionTestCase

from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import SYSTEM_EVENT_RT_TABLE_ID


class TestMigrations(TransactionTestCase):

    databases = {"default", "monitor_api"}

    @property
    def app(self):
        return django_apps.get_containing_app_config(type(self).__module__).name

    migrate_from = None
    migrate_to = None

    def setUp(self):
        assert (
            self.migrate_from and self.migrate_to
        ), "TestCase '{}' must define migrate_from and migrate_to properties".format(type(self).__name__)
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connections["monitor_api"])
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connections["monitor_api"])
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps: StateApps):
        pass


class TestStrategyMigrate(TestMigrations):
    migrate_from = "0031_auto_20210402_1803"
    migrate_to = "0032_migrate_strategy_config"

    BkMonitorTimeSeriesConfig = {
        "strategy": dict(
            bk_biz_id=2,
            id=1000,
            name="测试策略",
            source="bk_monitorv3",
            scenario="os",
            is_enabled=True,
        ),
        "query_config": dict(
            id=2000,
            result_table_id="system.disk",
            metric_field="usage",
            agg_method="AVG",
            agg_interval=60,
            agg_dimension=["bk_target_ip", "bk_target_cloud_id"],
            agg_condition=[],
            unit="percent",
            extend_fields={"origin_config": {"result_table_id": "system.disk", "metric_field": "usage"}},
        ),
        "item": dict(
            id=3000,
            name="测试指标",
            metric_id="system.disk.usage",
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.TIME_SERIES,
            no_data_config={},
            target=[
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0}, {"ip": "127.0.0.2", "bk_cloud_id": 0}],
                    }
                ]
            ],
        ),
        "algorithms": [
            dict(
                id=4000,
                algorithm_type="AdvancedRingRatio",
                algorithm_unit="K",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=1,
            ),
            dict(
                id=4001,
                algorithm_type="SimpleRingRatio",
                algorithm_unit="G",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=2,
            ),
        ],
    }

    LogSearchTimeSeriesConfig = {
        "strategy": dict(
            bk_biz_id=2,
            id=1001,
            name="测试策略",
            source="bk_monitorv3",
            scenario="os",
            is_enabled=True,
        ),
        "query_config": dict(
            id=2001,
            result_table_id="system.disk",
            metric_field="usage",
            agg_method="AVG",
            agg_interval=60,
            agg_dimension=["bk_target_ip", "bk_target_cloud_id"],
            agg_condition=[],
            unit="percent",
            extend_fields={"index_set_id": 1, "time_field": "@timestamp"},
        ),
        "item": dict(
            id=3001,
            name="测试指标",
            metric_id="system.disk.usage",
            data_source_label=DataSourceLabel.BK_LOG_SEARCH,
            data_type_label=DataTypeLabel.TIME_SERIES,
            no_data_config={},
            target=[[]],
        ),
        "algorithms": [
            dict(
                id=4003,
                algorithm_type="AdvancedRingRatio",
                algorithm_unit="K",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=1,
            ),
            dict(
                id=4004,
                algorithm_type="SimpleRingRatio",
                algorithm_unit="G",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=2,
            ),
        ],
    }

    LogSearchLogConfig = {
        "strategy": dict(
            bk_biz_id=2,
            id=1002,
            name="测试策略",
            source="bk_monitorv3",
            scenario="os",
            is_enabled=True,
        ),
        "query_config": dict(
            id=2002,
            result_table_id="索引集",
            keywords_query_string="level:error",
            rule="",
            keywords=[],
            agg_method="AVG",
            agg_interval=60,
            agg_dimension=["dimension1"],
            agg_condition=[],
            extend_fields={"index_set_id": 1, "time_field": "@timestamp"},
        ),
        "item": dict(
            id=3002,
            name="测试指标",
            metric_id="system.disk.usage",
            data_source_label=DataSourceLabel.BK_LOG_SEARCH,
            data_type_label=DataTypeLabel.LOG,
            no_data_config={},
            target=[[]],
        ),
        "algorithms": [
            dict(
                id=4005,
                algorithm_type="AdvancedRingRatio",
                algorithm_unit="K",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=1,
            ),
            dict(
                id=4006,
                algorithm_type="SimpleRingRatio",
                algorithm_unit="G",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=2,
            ),
        ],
    }

    BkMonitorEventConfig = {
        "strategy": dict(
            bk_biz_id=2,
            id=1003,
            name="测试策略",
            source="bk_monitorv3",
            scenario="os",
            is_enabled=True,
        ),
        "query_config": dict(
            id=2003,
            agg_condition=[{"key": "aaa", "method": "eq", "value": [1]}],
        ),
        "item": dict(
            id=3003,
            name="测试指标",
            metric_id="bk_monitor.gse-ping",
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.EVENT,
            no_data_config={},
            target=[[]],
        ),
        "algorithms": [
            dict(
                id=4007,
                algorithm_type="AdvancedRingRatio",
                algorithm_unit="K",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=1,
            )
        ],
    }

    BkMonitorEventConfigWithoutQuery = {
        "strategy": dict(
            bk_biz_id=2,
            id=1004,
            name="测试策略",
            source="bk_monitorv3",
            scenario="os",
            is_enabled=True,
        ),
        "item": dict(
            id=3004,
            name="测试指标",
            metric_id="bk_monitor.gse-ping",
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.EVENT,
            no_data_config={},
            target=[[]],
        ),
        "algorithms": [
            dict(
                id=4008,
                algorithm_type="AdvancedRingRatio",
                algorithm_unit="K",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=1,
            )
        ],
    }

    CustomEventConfig = {
        "strategy": dict(
            bk_biz_id=2,
            id=1005,
            name="测试策略",
            source="bk_monitorv3",
            scenario="os",
            is_enabled=True,
        ),
        "query_config": dict(
            id=2005,
            result_table_id="system.disk",
            agg_method="AVG",
            agg_interval=60,
            agg_dimension=["bk_target_ip", "bk_target_cloud_id"],
            agg_condition=[],
            extend_fields={"custom_event_name": "error"},
            bk_event_group_id=1,
            custom_event_id=1,
        ),
        "item": dict(
            id=3005,
            name="测试指标",
            metric_id="system.disk.usage",
            data_source_label=DataSourceLabel.CUSTOM,
            data_type_label=DataTypeLabel.EVENT,
            no_data_config={},
            target=[[]],
        ),
        "algorithms": [
            dict(
                id=4009,
                algorithm_type="AdvancedRingRatio",
                algorithm_unit="K",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=1,
            ),
            dict(
                id=4010,
                algorithm_type="SimpleRingRatio",
                algorithm_unit="G",
                algorithm_config={"floor": 1, "ceil": 1},
                trigger_config={},
                recovery_config={},
                message_template="",
                level=2,
            ),
        ],
    }

    @classmethod
    def create_strategy(cls, apps: StateApps):
        Strategy = apps.get_model("bkmonitor", "Strategy")
        Item = apps.get_model("bkmonitor", "Item")
        ResultTableSQLConfig = apps.get_model("bkmonitor", "ResultTableSQLConfig")
        ResultTableDSLConfig = apps.get_model("bkmonitor", "ResultTableDSLConfig")
        CustomEventQueryConfig = apps.get_model("bkmonitor", "CustomEventQueryConfig")
        BaseAlarmQueryConfig = apps.get_model("bkmonitor", "BaseAlarmQueryConfig")
        DetectAlgorithm = apps.get_model("bkmonitor", "DetectAlgorithm")

        strategy_types = [
            (ResultTableSQLConfig, cls.BkMonitorTimeSeriesConfig),
            (ResultTableSQLConfig, cls.LogSearchTimeSeriesConfig),
            (ResultTableDSLConfig, cls.LogSearchLogConfig),
            (BaseAlarmQueryConfig, cls.BkMonitorEventConfig),
            (BaseAlarmQueryConfig, cls.BkMonitorEventConfigWithoutQuery),
            (CustomEventQueryConfig, cls.CustomEventConfig),
        ]
        for model_class, config in strategy_types:
            strategy = Strategy.objects.create(**config["strategy"])
            if "query_config" in config:
                query_config = model_class.objects.create(**config["query_config"])
                query_config_id = query_config.id
            else:
                query_config_id = 0

            item = Item.objects.create(strategy_id=strategy.id, rt_query_config_id=query_config_id, **config["item"])
            for algorithm_config in config["algorithms"]:
                DetectAlgorithm.objects.create(strategy_id=strategy.id, item_id=item.id, **algorithm_config)

    def setUpBeforeMigration(self, apps: StateApps):
        self.create_strategy(apps)

    def test_migrated(self):
        from bkmonitor.models import (
            AlgorithmModel,
            DetectModel,
            ItemModel,
            QueryConfigModel,
            StrategyModel,
        )

        strategy = StrategyModel.objects.get(id=self.BkMonitorTimeSeriesConfig["strategy"]["id"])
        item = ItemModel.objects.get(id=self.BkMonitorTimeSeriesConfig["item"]["id"])
        query_config = QueryConfigModel.objects.filter(strategy_id=strategy.id).first()
        detect1, detect2 = DetectModel.objects.filter(strategy_id=strategy.id)
        algorithm1, algorithm2 = AlgorithmModel.objects.filter(strategy_id=strategy.id)
        for field in self.BkMonitorTimeSeriesConfig["strategy"]:
            assert getattr(strategy, field) == self.BkMonitorTimeSeriesConfig["strategy"][field]

        assert query_config.config["result_table_id"] == "system.disk"
        assert query_config.config["metric_field"] == "usage"
        assert query_config.config["agg_method"] == "AVG"
        assert query_config.config["agg_interval"] == 60
        assert query_config.config["agg_dimension"] == ["bk_target_ip", "bk_target_cloud_id"]
        assert query_config.config["agg_condition"] == []
        assert query_config.config["unit"] == "percent"
        assert query_config.config["origin_config"] == {"result_table_id": "system.disk", "metric_field": "usage"}
        assert query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert query_config.data_type_label == DataTypeLabel.TIME_SERIES
        assert item.id == 3000
        assert item.name == "测试指标"
        assert item.target == [
            [
                {
                    "field": "bk_target_ip",
                    "method": "eq",
                    "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0}, {"ip": "127.0.0.2", "bk_cloud_id": 0}],
                }
            ]
        ]
        assert detect1.level == 1
        assert detect2.level == 2
        assert algorithm1.level == 1
        assert algorithm1.type == "AdvancedRingRatio"
        assert algorithm1.unit_prefix == "K"
        assert algorithm2.level == 2
        assert algorithm2.type == "SimpleRingRatio"
        assert algorithm2.unit_prefix == "G"

        strategy = StrategyModel.objects.get(id=self.LogSearchLogConfig["strategy"]["id"])
        item = ItemModel.objects.get(id=self.LogSearchLogConfig["item"]["id"])
        query_config = QueryConfigModel.objects.filter(strategy_id=strategy.id).first()
        detect1, detect2 = DetectModel.objects.filter(strategy_id=strategy.id)
        algorithm1, algorithm2 = AlgorithmModel.objects.filter(strategy_id=strategy.id)
        for field in self.LogSearchLogConfig["strategy"]:
            assert getattr(strategy, field) == self.LogSearchLogConfig["strategy"][field]

        assert query_config.config["query_string"] == "level:error"
        assert query_config.config["agg_interval"] == 60
        assert query_config.config["agg_dimension"] == ["dimension1"]
        assert query_config.config["agg_condition"] == []
        assert query_config.config["index_set_id"] == 1
        assert query_config.config["time_field"] == "@timestamp"
        assert query_config.data_source_label == DataSourceLabel.BK_LOG_SEARCH
        assert query_config.data_type_label == DataTypeLabel.LOG
        assert item.id == 3002
        assert item.name == "测试指标"
        assert item.target == [[]]
        assert detect1.level == 1
        assert detect2.level == 2
        assert algorithm1.level == 1
        assert algorithm1.type == "AdvancedRingRatio"
        assert algorithm1.unit_prefix == "K"
        assert algorithm2.level == 2
        assert algorithm2.type == "SimpleRingRatio"
        assert algorithm2.unit_prefix == "G"

        strategy = StrategyModel.objects.get(id=self.BkMonitorEventConfig["strategy"]["id"])
        item = ItemModel.objects.get(id=self.BkMonitorEventConfig["item"]["id"])
        query_config = QueryConfigModel.objects.filter(strategy_id=strategy.id).first()
        detect = DetectModel.objects.filter(strategy_id=strategy.id).first()
        algorithm = AlgorithmModel.objects.filter(strategy_id=strategy.id).first()
        for field in self.BkMonitorEventConfig["strategy"]:
            assert getattr(strategy, field) == self.BkMonitorEventConfig["strategy"][field]
        assert query_config.config["result_table_id"] == SYSTEM_EVENT_RT_TABLE_ID
        assert query_config.config["metric_field"] == "gse-ping"
        assert query_config.config["agg_condition"] == [{"key": "aaa", "method": "eq", "value": [1]}]
        assert query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert query_config.data_type_label == DataTypeLabel.EVENT
        assert item.id == 3003
        assert item.name == "测试指标"
        assert item.target == [[]]
        assert detect.level == 1
        assert algorithm.level == 1
        assert algorithm.type == "AdvancedRingRatio"
        assert algorithm.unit_prefix == "K"

        strategy = StrategyModel.objects.get(id=self.BkMonitorEventConfigWithoutQuery["strategy"]["id"])
        item = ItemModel.objects.get(id=self.BkMonitorEventConfigWithoutQuery["item"]["id"])
        query_config = QueryConfigModel.objects.filter(strategy_id=strategy.id).first()
        detect = DetectModel.objects.filter(strategy_id=strategy.id).first()
        algorithm = AlgorithmModel.objects.filter(strategy_id=strategy.id).first()
        for field in self.BkMonitorEventConfigWithoutQuery["strategy"]:
            assert getattr(strategy, field) == self.BkMonitorEventConfigWithoutQuery["strategy"][field]
        assert query_config.config["result_table_id"] == SYSTEM_EVENT_RT_TABLE_ID
        assert query_config.config["metric_field"] == "gse-ping"
        assert query_config.config["agg_condition"] == []
        assert query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert query_config.data_type_label == DataTypeLabel.EVENT
        assert item.id == 3004
        assert item.name == "测试指标"
        assert item.target == [[]]
        assert detect.level == 1
        assert algorithm.level == 1
        assert algorithm.type == "AdvancedRingRatio"
        assert algorithm.unit_prefix == "K"

        strategy = StrategyModel.objects.get(id=self.CustomEventConfig["strategy"]["id"])
        item = ItemModel.objects.get(id=self.CustomEventConfig["item"]["id"])
        query_config = QueryConfigModel.objects.filter(strategy_id=strategy.id).first()
        detect1, detect2 = DetectModel.objects.filter(strategy_id=strategy.id)
        algorithm1, algorithm2 = AlgorithmModel.objects.filter(strategy_id=strategy.id)
        for field in self.CustomEventConfig["strategy"]:
            assert getattr(strategy, field) == self.CustomEventConfig["strategy"][field]

        assert query_config.config["result_table_id"] == "system.disk"
        assert query_config.config["agg_method"] == "AVG"
        assert query_config.config["agg_interval"] == 60
        assert query_config.config["agg_dimension"] == ["bk_target_ip", "bk_target_cloud_id"]
        assert query_config.config["agg_condition"] == []
        assert query_config.config["custom_event_name"] == "error"
        assert query_config.data_source_label == DataSourceLabel.CUSTOM
        assert query_config.data_type_label == DataTypeLabel.EVENT
        assert item.id == 3005
        assert item.name == "测试指标"
        assert item.target == [[]]
        assert detect1.level == 1
        assert detect2.level == 2
        assert algorithm1.level == 1
        assert algorithm1.type == "AdvancedRingRatio"
        assert algorithm1.unit_prefix == "K"
        assert algorithm2.level == 2
        assert algorithm2.type == "SimpleRingRatio"
        assert algorithm2.unit_prefix == "G"


class TestUptimeCheckStrategyMigrations(TestMigrations):
    migrate_from = "0036_fix_metric_changed_from_v2_5"
    migrate_to = "0037_fix_uptime_check_strategy"

    QueryConfig = {
        "strategy_id": 1,
        "item_id": 1,
        "data_source_label": "bk_monitor",
        "data_type_label": "time_series",
        "alias": "a",
        "config": {
            "unit": "",
            "agg_method": "COUNT",
            "agg_interval": 60,
            "metric_field": "node_id",
            "agg_condition": [{"key": "error_code", "value": 3002, "method": "eq"}],
            "agg_dimension": ["task_id"],
            "result_table_id": "uptimecheck.http",
        },
    }

    def setUpBeforeMigration(self, apps: StateApps):
        QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
        QueryConfigModel.objects.all().delete()
        QueryConfigModel.objects.create(**self.QueryConfig)

    def test_migrated(self):
        from bkmonitor.models import QueryConfigModel

        q = QueryConfigModel.objects.first()
        assert q.config["metric_field"] == "available"
        assert q.config["agg_condition"] == [{"key": "error_code", "value": ["3002"], "method": "eq"}]
