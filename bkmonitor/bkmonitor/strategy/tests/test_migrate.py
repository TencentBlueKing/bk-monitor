# -*- coding: utf-8 -*-
import random
import typing
from copy import deepcopy

import pytest
from django.apps import apps
from django.core.management import call_command

from bkmonitor.models import ActionConfig, StrategyActionConfigRelation, StrategyModel
from bkmonitor.strategy.migrate import update_notice_template
from bkmonitor.strategy.new_strategy import Strategy
from constants import alert as alert_constants

pytestmark = pytest.mark.django_db


BIZ_SCOPE: typing.List[int] = list(range(1, 10))


def assert_template(action_configs: typing.List[ActionConfig], expect: str):
    for action_config in action_configs:
        assert action_config.hash == ""
        assert action_config.snippet == ""
        for template in action_config.execute_config["template_detail"]["template"]:
            assert template["message_tmpl"] == expect


@pytest.fixture
def strategy_factory():
    def _inner(_config: typing.Dict, _count: int):

        for template in _config["notice"]["config"]["template"]:
            template["message_tmpl"] = alert_constants.OLD_DEFAULT_TEMPLATE

        strategy_ids: typing.List[int] = []
        for idx in range(_count):
            strategy = Strategy(
                **{**_config, "name": f"{_config['name']}_{idx}", "bk_biz_id": random.choice(BIZ_SCOPE)}
            )
            strategy.save()
            strategy_ids.append(strategy.to_dict()["id"])

        config_id__strategy_id: typing.Dict[int, int] = {}
        strategy_relate_infos: typing.List[typing.Dict[str, typing.Any]] = []
        for relation in StrategyActionConfigRelation.objects.filter(strategy_id__in=strategy_ids).values(
            "strategy_id", "config_id"
        ):
            config_id__strategy_id[relation["config_id"]] = relation["strategy_id"]

        config_ids: typing.List[int] = []
        action_configs: typing.List[ActionConfig] = ActionConfig.objects.filter(id__in=config_id__strategy_id.keys())
        for action_config in action_configs:
            config_ids.append(action_config.id)
            strategy_relate_infos.append(
                {"config_id": action_config.id, "strategy_id": config_id__strategy_id[action_config.id]}
            )

        # 业务逻辑里的 hash 需要通过配置 md5 进行计算，参考：bkmonitor.as_code.parse.convert_rules
        # 这里仅验证 hash 和 snippet 可以被重置
        StrategyModel.objects.filter(id__in=strategy_ids).update(hash="123", snippet="123")
        ActionConfig.objects.filter(id__in=config_ids).update(hash="123", snippet="123")

        return strategy_relate_infos

    return _inner


class TestMigrate:
    Config = {
        "type": "monitor",
        "bk_biz_id": 11,
        "scenario": "os",
        "name": "test",
        "is_enabled": True,
        "priority": 100,
        "items": [
            {
                "name": "AVG(物理内存已用占比)",
                "no_data_config": {
                    "continuous": 10,
                    "is_enabled": False,
                    "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                    "level": 2,
                },
                "target": [],
                "expression": "a",
                "functions": [],
                "origin_sql": "",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "result_table_id": "system.mem",
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                        "agg_condition": [
                            {
                                "key": "bk_target_ip",
                                "value": ["127.0.0.1"],
                                "method": "eq",
                                "condition": "and",
                                "dimension_name": "目标IP",
                            }
                        ],
                        "metric_field": "psc_pct_used",
                        "unit": "percent",
                        "metric_id": "bk_monitor.system.mem.psc_pct_used",
                        "index_set_id": "",
                        "query_string": "*",
                        "custom_event_name": "psc_pct_used",
                        "functions": [],
                        "time_field": "time",
                        "bkmonitor_strategy_id": "psc_pct_used",
                        "alert_name": "psc_pct_used",
                    }
                ],
                "algorithms": [
                    {
                        "level": 1,
                        "type": "Threshold",
                        "config": [[{"method": "gte", "threshold": 80}]],
                        "unit_prefix": "%",
                    }
                ],
            }
        ],
        "detects": [
            {
                "level": 1,
                "expression": "",
                "trigger_config": {
                    "count": 2,
                    "check_window": 5,
                    "uptime": {"calendars": [], "time_ranges": [{"start": "00:00", "end": "23:59"}]},
                },
                "recovery_config": {"check_window": 5},
                "connector": "and",
            }
        ],
        "notice": {
            "user_groups": [808],
            "signal": ["abnormal", "no_data"],
            "options": {
                "converge_config": {"need_biz_converge": False},
                "exclude_notice_ways": {"recovered": [], "closed": [], "ack": []},
                "noise_reduce_config": {"dimensions": [], "is_enabled": False, "count": 10},
                "upgrade_config": {"is_enabled": False, "user_groups": [], "upgrade_interval": 1440},
                "assign_mode": ["by_rule", "only_notice"],
                "chart_image_enabled": True,
            },
            "relate_type": "NOTICE",
            "config": {
                "need_poll": True,
                "notify_interval": 300,
                "interval_notify_mode": "standard",
                "template": deepcopy(alert_constants.DEFAULT_NOTICE_MESSAGE_TEMPLATE),
            },
        },
        "metric_type": "time_series",
    }

    @pytest.mark.parametrize(
        "count, bk_biz_ids, rollback, use_cmd",
        [
            pytest.param(1, None, False, False, id="all[count=1]"),
            pytest.param(1000, None, False, False, id="all[count=1000]"),
            pytest.param(10, random.choices(BIZ_SCOPE, k=1), False, False, id="single[count=10]"),
            pytest.param(10, random.choices(BIZ_SCOPE, k=5), False, False, id="partial[count=10]"),
            pytest.param(1000, random.choices(BIZ_SCOPE, k=1), False, False, id="single[count=1000]"),
            pytest.param(1000, random.choices(BIZ_SCOPE, k=5), False, False, id="partial[count=1000]"),
            pytest.param(100, None, True, False, id="all[count=100|rollback]"),
            pytest.param(100, random.choices(BIZ_SCOPE, k=5), True, False, id="partial[count=100|rollback]"),
            pytest.param(10, None, False, True, id="all[count=10|use_cmd]"),
            pytest.param(10, random.choices(BIZ_SCOPE, k=1), False, True, id="single[count=10|use_cmd]"),
            pytest.param(10, random.choices(BIZ_SCOPE, k=1), True, True, id="single[count=10|rollback|use_cmd]"),
            pytest.param(10, random.choices(BIZ_SCOPE, k=5), False, True, id="partial[count=10|use_cmd]"),
        ],
    )
    def test_migrate(
        self,
        clean_model,
        strategy_factory,
        count: int,
        bk_biz_ids: typing.Optional[typing.List[int]],
        rollback: bool,
        use_cmd: bool,
    ):

        strategy_relate_infos: typing.List[typing.Dict[str, typing.Any]] = strategy_factory(self.Config, count)

        update_count: typing.Optional[int] = None
        if use_cmd:
            call_command("update_notice_template", bk_biz_ids=bk_biz_ids)
        else:
            update_count: int = update_notice_template(
                apps,
                old=alert_constants.OLD_DEFAULT_TEMPLATE,
                new=alert_constants.DEFAULT_TEMPLATE,
                bk_biz_ids=bk_biz_ids,
            )

        query_kwargs = {"bk_biz_id__in": bk_biz_ids or BIZ_SCOPE}
        strategy_ids: typing.Set[int] = set(StrategyModel.objects.filter(**query_kwargs).values_list("id", flat=True))
        config_ids: typing.List[int] = [
            strategy_relate_info["config_id"]
            for strategy_relate_info in strategy_relate_infos
            if strategy_relate_info["strategy_id"] in strategy_ids
        ]

        if update_count is not None:
            assert len(strategy_ids) == update_count

        assert_template(ActionConfig.objects.filter(id__in=config_ids), alert_constants.DEFAULT_TEMPLATE)
        assert StrategyModel.objects.filter(**{**query_kwargs, "hash": "", "snippet": ""}).count() == len(strategy_ids)

        if rollback:
            rollback_count: typing.Optional[int] = None
            if use_cmd:
                call_command("update_notice_template", bk_biz_ids=bk_biz_ids, rollback=True)
            else:
                rollback_count: int = update_notice_template(
                    apps,
                    old=alert_constants.DEFAULT_TEMPLATE,
                    new=alert_constants.OLD_DEFAULT_TEMPLATE,
                    bk_biz_ids=bk_biz_ids,
                )
            if update_count is not None:
                assert StrategyModel.objects.filter(**query_kwargs).count() == rollback_count

            assert_template(ActionConfig.objects.filter(id__in=config_ids), alert_constants.OLD_DEFAULT_TEMPLATE)
