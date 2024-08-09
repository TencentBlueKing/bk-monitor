# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from django.db.transaction import atomic
from django.utils.translation import ugettext as _

from apps.api import MonitorApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.log_clustering.constants import (
    AGG_CONDITION,
    AGG_DIMENSION,
    ALARM_INTERVAL_CLUSTERING,
    DEFAULT_AGG_METHOD,
    DEFAULT_DATA_SOURCE_LABEL_BKDATA,
    DEFAULT_DATA_TYPE_LABEL_BKDATA,
    DEFAULT_EXPRESSION,
    DEFAULT_LABEL,
    DEFAULT_METRIC_CLUSTERING,
    DEFAULT_NO_DATA_CONFIG,
    DEFAULT_PATTERN_MONITOR_MSG,
    DEFAULT_SCENARIO,
    ITEM_NAME_CLUSTERING,
    TRIGGER_CONFIG,
    StrategiesType,
)
from apps.log_clustering.exceptions import ClusteringIndexSetNotExistException
from apps.log_clustering.models import ClusteringConfig, SignatureStrategySettings
from apps.log_search.models import LogIndexSet


class ClusteringMonitorHandler(object):
    def __init__(self, index_set_id):
        self.index_set_id = index_set_id
        self.index_set = LogIndexSet.objects.filter(index_set_id=self.index_set_id).first()
        if not self.index_set:
            raise ClusteringIndexSetNotExistException(
                ClusteringIndexSetNotExistException.MESSAGE.format(index_set_id=self.index_set_id)
            )
        self.log_index_set_data, *_ = self.index_set.indexes
        self.clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id)
        self.bk_biz_id = (
            self.clustering_config.bk_biz_id
            if not self.clustering_config.related_space_pre_bk_biz_id
            else self.clustering_config.related_space_pre_bk_biz_id
        )
        self.conf = FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config

    @atomic
    def save_clustering_strategy(
        self,
        pattern_level="",
        table_id=None,
        metric="",
        strategy_type=StrategiesType.NEW_CLS_strategy,  # 新类告警
        params=None,
    ):
        params = params or {}
        signature_strategy_settings, created = SignatureStrategySettings.objects.get_or_create(
            index_set_id=self.index_set_id,
            strategy_type=strategy_type,
            signature="",
            is_deleted=False,
            defaults={
                "strategy_id": None,
                "bk_biz_id": self.bk_biz_id,
                "pattern_level": pattern_level,
            },
        )
        anomaly_template = DEFAULT_PATTERN_MONITOR_MSG.replace(
            "__clustering_field__", self.clustering_config.clustering_fields
        )
        label_index_set_id = self.clustering_config.new_cls_index_set_id or self.index_set_id

        labels = DEFAULT_LABEL.copy()
        labels += [f"LogClustering/Count/{label_index_set_id}"]
        if strategy_type == StrategiesType.NORMAL_STRATEGY:
            name = _("{} - 日志数量突增异常告警").format(self.index_set.index_set_name)
            args = {
                "$alert_down": "1",
                "$sensitivity": params["sensitivity"],
                "$alert_upward": "1",
            }

        else:
            name = _("{} - 日志新类异常告警").format(self.index_set.index_set_name)
            args = {
                "$model_file_id": self.clustering_config.model_output_rt,  # 预测节点输出
                "$new_class_interval": params["interval"],
                "$new_class_alert_th": params["threshold"],
            }
        items = [
            {
                "name": ITEM_NAME_CLUSTERING,
                "no_data_config": DEFAULT_NO_DATA_CONFIG,
                "target": [],
                "expression": DEFAULT_EXPRESSION,
                "functions": [],
                "origin_sql": "",
                "query_configs": [
                    {
                        "data_source_label": DEFAULT_DATA_SOURCE_LABEL_BKDATA,
                        "data_type_label": DEFAULT_DATA_TYPE_LABEL_BKDATA,
                        "alias": DEFAULT_EXPRESSION,
                        "result_table_id": table_id,
                        "agg_method": DEFAULT_AGG_METHOD,
                        "agg_interval": self.conf.get("agg_interval", 60),
                        "agg_dimension": AGG_DIMENSION,
                        "agg_condition": AGG_CONDITION,
                        "metric_field": metric,
                        "unit": "",
                        "metric_id": "bk_data.{table_id}.{metric}".format(table_id=table_id, metric=metric),
                        "index_set_id": "",
                        "query_string": "*",
                        "custom_event_name": "log_count",
                        "functions": [],
                        "time_field": "dtEventTimeStamp",
                        "bkmonitor_strategy_id": "log_count",
                        "alert_name": "log_count",
                    }
                ],
                "algorithms": [
                    {
                        "level": params["level"],
                        "type": "IntelligentDetect",
                        "config": {
                            "plan_id": self.conf.get("normal_plan_id")
                            if strategy_type == StrategiesType.NORMAL_STRATEGY
                            else self.conf.get("algorithm_plan_id"),
                            "visual_type": "score",
                            "args": args,
                        },
                        "unit_prefix": "",
                    }
                ],
            }
        ]
        detects = [
            {
                "level": 2,
                "expression": "",
                "trigger_config": TRIGGER_CONFIG,
                "recovery_config": {"check_window": 5},
                "connector": "and",
            }
        ]
        notice = {
            "config_id": 0,
            "user_groups": params["user_groups"],
            "signal": ["abnormal"],
            "options": {
                "converge_config": {"need_biz_converge": True},
                "exclude_notice_ways": {"recovered": [], "closed": [], "ack": []},
                "noise_reduce_config": {"is_enabled": False, "count": 10, "dimensions": []},
                "upgrade_config": {"is_enabled": False, "user_groups": []},
                "assign_mode": ["by_rule", "only_notice"],
                "chart_image_enabled": False,
            },
            "config": {
                "interval_notify_mode": "standard",
                "notify_interval": ALARM_INTERVAL_CLUSTERING,
                "template": [
                    {
                        "signal": "abnormal",
                        "message_tmpl": anomaly_template,
                        "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                    }
                ],
            },
        }
        request_params = {
            "type": "monitor",
            "bk_biz_id": self.bk_biz_id,
            "scenario": DEFAULT_SCENARIO,
            "name": name,
            "labels": labels,
            "is_enabled": True,
            "items": items,
            "detects": detects,
            "actions": [],
            "notice": notice,
        }
        if signature_strategy_settings.strategy_id:
            # 更新告警策略
            request_params["id"] = signature_strategy_settings.strategy_id
        strategy = MonitorApi.save_alarm_strategy_v3(params=request_params)
        strategy_id = strategy["id"]
        signature_strategy_settings.strategy_id = strategy_id
        signature_strategy_settings.save()

        self.clustering_config.log_count_agg_rt = f"{table_id}_{strategy_id}_plan_{self.conf.get('algorithm_plan_id')}"
        self.clustering_config.save()
        return {"strategy_id": strategy_id, "label_name": labels}

    def get_strategy(self, strategy_type, strategy_id):
        # 获取告警策略信息
        conditions = [{"key": "strategy_id", "value": [strategy_id]}]
        result_data = MonitorApi.search_alarm_strategy_v3({"bk_biz_id": self.bk_biz_id, "conditions": conditions})
        if not result_data["strategy_config_list"]:
            return {}
        strategy_config = result_data["strategy_config_list"][0]
        algorithms_config = strategy_config["items"][0]["algorithms"][0]
        level = algorithms_config["level"]
        user_groups = strategy_config["notice"]["user_groups"]
        labels = strategy_config["labels"]
        data = {"strategy_id": strategy_id, "level": level, "user_groups": user_groups, "label_name": labels}
        if strategy_type == StrategiesType.NEW_CLS_strategy:
            interval = algorithms_config["config"]["args"].get("$new_class_interval", "")
            threshold = algorithms_config["config"]["args"].get("$new_class_alert_th", "")
            data.update({"interval": interval, "threshold": threshold})
        else:
            sensitivity = algorithms_config["config"]["args"].get("$sensitivity", "")
            data.update({"sensitivity": sensitivity})
        return data

    @atomic
    def delete_strategy(self, strategy_type):
        obj = SignatureStrategySettings.objects.filter(
            index_set_id=self.index_set_id,
            strategy_type=strategy_type,
            signature="",
        ).first()
        if not obj or not obj.strategy_id:
            return ""
        strategy_id = obj.strategy_id
        obj.delete()
        MonitorApi.delete_alarm_strategy_v3(params={"bk_biz_id": self.bk_biz_id, "ids": [strategy_id]})
        return strategy_id

    def create_or_update_clustering_strategy(self, params, strategy_type):
        # 创建/更新 新类或数量突增报警
        table_id = (
            self.clustering_config.new_cls_pattern_rt
            if self.clustering_config.new_cls_pattern_rt
            else self.clustering_config.log_count_aggregation_flow["log_count_aggregation"]["result_table_id"]
        )
        return self.save_clustering_strategy(
            table_id=table_id,
            metric=DEFAULT_METRIC_CLUSTERING,
            strategy_type=strategy_type,
            params=params,
        )
