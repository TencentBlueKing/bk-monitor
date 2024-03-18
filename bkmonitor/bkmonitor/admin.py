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

import inspect
import json

from django.contrib import admin
from django.forms import widgets

from bkmonitor import models
from bkmonitor.utils.db import JsonField


class StrategyAdmin(admin.ModelAdmin):
    list_display = ("name", "bk_biz_id", "source", "scenario", "target", "update_time")
    search_fields = ("name", "bk_biz_id", "source", "scenario")
    list_filter = ("bk_biz_id", "scenario")


class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "metric_id",
        "data_source_label",
        "data_type_label",
        "rt_query_config_id",
        "no_data_config",
        "update_time",
    )
    search_fields = ("name", "metric_id", "data_source_label", "data_type_label")
    list_filter = ("metric_id", "data_source_label", "data_type_label")


class ResultTableSQLConfigAdmin(admin.ModelAdmin):
    list_display = (
        "result_table_id",
        "metric_field",
        "agg_method",
        "agg_interval",
        "agg_dimension",
        "agg_condition",
        "unit",
        "unit_conversion",
    )
    search_fields = ("result_table_id", "metric_field", "agg_method", "agg_interval")
    list_filter = ("agg_method",)


class ResultTableDSLConfigAdmin(admin.ModelAdmin):
    list_display = (
        "result_table_id",
        "agg_method",
        "agg_interval",
        "agg_dimension",
        "keywords_query_string",
        "rule",
        "keywords",
    )
    search_fields = ("result_table_id", "keywords_query_string", "agg_method", "rule", "keywords")
    list_filter = ("agg_method",)


class DetectAlgorithmAdmin(admin.ModelAdmin):
    list_display = (
        "algorithm_type",
        "level",
        "algorithm_config",
        "trigger_config",
        "recovery_config",
        "message_template",
        "item_id",
        "update_time",
    )
    search_fields = ("algorithm_type", "level", "item_id", "strategy_id")
    list_filter = ("algorithm_type", "level")


class ActionAdmin(admin.ModelAdmin):
    list_display = ("action_type", "config", "strategy_id", "update_time")
    search_fields = ("action_type", "strategy_id")
    list_filter = ("action_type",)


class NoticeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "bk_biz_id", "notice_receiver", "notice_way", "message", "update_time")
    search_fields = ("name", "bk_biz_id", "notice_way", "notice_receiver")
    list_filter = ("bk_biz_id", "notice_way")


class AnomalyRecordAdmin(admin.ModelAdmin):
    list_display = ("anomaly_id", "source_time", "strategy_id", "event_id")
    search_fields = ("anomaly_id", "source_time", "strategy_id", "event_id")


class EventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "begin_time", "end_time", "bk_biz_id", "level", "status", "is_ack", "strategy_id")
    search_fields = ("bk_biz_id", "event_id", "level", "status", "strategy_id")
    list_filter = ("bk_biz_id", "level", "status", "strategy_id")


class EventActionAdmin(admin.ModelAdmin):
    list_display = ("create_time", "username", "operate", "message", "status", "event_id")
    search_fields = ("create_time", "username", "operate", "message", "status", "event_id")
    list_filter = ("username", "operate", "status")


class AlertAdmin(admin.ModelAdmin):
    list_display = ("method", "username", "role", "create_time", "status", "action_id", "event_id")
    search_fields = ("method", "username", "action_id", "event_id", "status", "create_time")
    list_filter = ("method", "status")


class ShieldAdmin(admin.ModelAdmin):
    list_display = (
        "category",
        "bk_biz_id",
        "scope_type",
        "content",
        "begin_time",
        "end_time",
        "failure_time",
        "description",
    )
    search_fields = ("category", "bk_biz_id", "scope_type", "content", "begin_time")
    list_filter = ("category", "bk_biz_id", "scope_type")


class PrettyJSONWidget(widgets.Textarea):
    def render(self, name, value, attrs=None, renderer=None):
        try:
            value = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split("\n")]
            self.attrs["rows"] = min(max(len(row_lengths) + 2, 10), 30)
            self.attrs["cols"] = min(max(max(row_lengths) + 2, 40), 120)
        except Exception:  # noqa
            pass
        return super(PrettyJSONWidget, self).render(name, value, attrs, renderer)


class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ("description", "key", "value", "data_type")
    search_fields = ("description", "key")
    list_filter = ("is_advanced",)

    formfield_overrides = {JsonField: {"widget": PrettyJSONWidget}}

    def changelist_view(self, request, extra_context=None):
        if "is_advanced__exact" not in request.GET:
            q = request.GET.copy()
            q["is_advanced__exact"] = "0"
            request.GET = q
            request.META["QUERY_STRING"] = request.GET.urlencode()
        return super(GlobalConfigAdmin, self).changelist_view(request, extra_context=extra_context)


class HealthzMetricConfigAdmin(admin.ModelAdmin):
    list_display = ("node_name", "category", "collect_metric", "collect_type", "collect_interval", "metric_alias")
    search_fields = ("collect_type", "node_name", "category", "metric_alias")
    list_filter = ("collect_type", "node_name", "category", "metric_alias")


class HealthzTopoNodeAdmin(admin.ModelAdmin):
    list_display = ("node_name",)
    search_fields = ("node_name",)
    list_filter = ("node_name",)


class HealthzMetricRecordAdmin(admin.ModelAdmin):
    list_display = ("metric_alias", "server_ip", "last_update")
    search_fields = ("metric_alias", "server_ip", "last_update")
    list_filter = ("metric_alias", "server_ip", "last_update")


class AlertCollectAdmin(admin.ModelAdmin):
    list_display = ("collect_key", "collect_type", "message", "extend_info", "collect_time")
    search_fields = ("collect_key", "collect_type", "message", "extend_info", "collect_time")
    list_filter = ("collect_key", "collect_type", "collect_time")


class ActionNoticeMappingAdmin(admin.ModelAdmin):
    list_display = ("action_id", "notice_group_id")
    search_fields = ("action_id", "notice_group_id")
    list_filter = ("notice_group_id",)


class NoticeTemplateAdmin(admin.ModelAdmin):
    list_display = ("anomaly_template", "recovery_template", "action_id")
    search_fields = ("anomaly_template", "recovery_template", "action_id")
    list_filter = ("action_id",)


class CustomEventQueryConfigAdmin(admin.ModelAdmin):
    list_display = (
        "bk_event_group_id",
        "custom_event_id",
        "agg_dimension",
        "agg_condition",
        "agg_method",
        "agg_interval",
        "extend_fields",
        "result_table_id",
    )
    search_fields = (
        "bk_event_group_id",
        "custom_event_id",
        "agg_dimension",
        "agg_condition",
        "agg_method",
        "agg_interval",
        "extend_fields",
        "result_table_id",
    )
    list_filter = (
        "bk_event_group_id",
        "custom_event_id",
        "agg_dimension",
        "agg_condition",
        "agg_method",
        "agg_interval",
        "extend_fields",
        "result_table_id",
    )


class BaseAlarmAdmin(admin.ModelAdmin):
    list_display = ("alarm_type", "title", "description", "is_enable")
    search_fields = ("alarm_type", "title", "description")
    list_filter = ("alarm_type", "title", "description", "is_enable")


class SnapshotHostIndexAdmin(admin.ModelAdmin):
    list_display = (
        "category",
        "item",
        "type",
        "result_table_id",
        "dimension_field",
        "conversion",
        "conversion_unit",
        "metric",
        "is_linux",
        "is_windows",
        "is_aix",
    )
    search_fields = (
        "category",
        "item",
        "type",
        "result_table_id",
        "dimension_field",
        "conversion",
        "conversion_unit",
        "metric",
    )
    list_filter = (
        "category",
        "type",
        "result_table_id",
        "dimension_field",
        "conversion",
        "conversion_unit",
        "is_linux",
        "is_windows",
        "is_aix",
    )


class ApiAuthTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "namespaces", "type", "expire_time", "params")
    search_fields = ("name", "namespaces")
    list_filter = ("type",)


class StatisticsMetricAdmin(admin.ModelAdmin):
    list_display = ("name", "update_time")
    search_fields = ("name",)


class AIFeatureSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "bk_biz_id",
        "config",
        "create_at",
        "update_at",
    )
    search_fields = ("bk_biz_id",)
    list_filter = ("bk_biz_id",)

    formfield_overrides = {JsonField: {"widget": PrettyJSONWidget}}


admin.site.register(models.Strategy, StrategyAdmin)
admin.site.register(models.Item, ItemAdmin)
admin.site.register(models.ResultTableSQLConfig, ResultTableSQLConfigAdmin)
admin.site.register(models.ResultTableDSLConfig, ResultTableDSLConfigAdmin)
admin.site.register(models.DetectAlgorithm, DetectAlgorithmAdmin)
admin.site.register(models.Action, ActionAdmin)
admin.site.register(models.NoticeGroup, NoticeGroupAdmin)
admin.site.register(models.AnomalyRecord, AnomalyRecordAdmin)
admin.site.register(models.Event, EventAdmin)
admin.site.register(models.EventAction, EventActionAdmin)
admin.site.register(models.Alert, AlertAdmin)
admin.site.register(models.Shield, ShieldAdmin)
admin.site.register(models.GlobalConfig, GlobalConfigAdmin)
admin.site.register(models.HealthzMetricConfig, HealthzMetricConfigAdmin)
admin.site.register(models.HealthzTopoNode, HealthzTopoNodeAdmin)
admin.site.register(models.HealthzMetricRecord, HealthzMetricRecordAdmin)
admin.site.register(models.AlertCollect, AlertCollectAdmin)
admin.site.register(models.ActionNoticeMapping, ActionNoticeMappingAdmin)
admin.site.register(models.NoticeTemplate, NoticeTemplateAdmin)
admin.site.register(models.CustomEventQueryConfig, CustomEventQueryConfigAdmin)
admin.site.register(models.BaseAlarm, BaseAlarmAdmin)
admin.site.register(models.SnapshotHostIndex, SnapshotHostIndexAdmin)
admin.site.register(models.StrategyModel, models.StrategyModelAdmin)
admin.site.register(models.ItemModel, models.ItemModelAdmin)
admin.site.register(models.QueryConfigModel, models.QueryConfigModelAdmin)
admin.site.register(models.AlgorithmModel, models.AlgorithmModelAdmin)
admin.site.register(models.DetectModel, models.DetectModelAdmin)
admin.site.register(models.StrategyHistoryModel, models.StrategyHistoryModelAdmin)
admin.site.register(models.ApiAuthToken, ApiAuthTokenAdmin)
admin.site.register(models.StatisticsMetric, StatisticsMetricAdmin)
admin.site.register(models.AIFeatureSettings, AIFeatureSettingsAdmin)


# 因为配置admin界面时，list_display, search_fields, list_filter 都是全部字段中排除效果不好的几个，
# 所以在这里对每个model名称后面提供这三个选项要排除的字段，并以全小写提供。
model_admins = [
    ["EventPlugin", (), (), ("id", "plugin_id")],
    ["AlertConfig", (), ("rules",), ("id", "rules", "order")],
    [
        "ActionInstance",
        (
            "inputs",
            "outputs",
            "action_config",
            "action_plugin",
            "ex_data",
            "generate_uuid",
        ),
        ("id", "alerts", "action_config", "plugin_config", "strategy"),
        (
            "id",
            "alerts",
            "generate_uuid",
            "execute_times",
            "inputs",
            "outputs",
            "action_config",
            "action_plugin",
            "ex_data",
            "strategy",
        ),
    ],
    ["ActionInstanceLog", ("content"), (), ("id", "content")],
    ["ConvergeInstance", (), ("id", "content", "detail"), ("id", "converge_config", "content", "detail")],
    ["ConvergeRelation", ("id"), ("id"), ("id")],
]

for model_name, list_display_exclude, search_fields_exclude, list_filter_exclude in model_admins:
    model_class = getattr(models.fta, model_name)
    fields = [field.name for field in model_class._meta.fields if field.name in model_class.__dict__]
    admin.site.register(
        model_class,
        list_display=[field for field in fields if field.lower() not in list_display_exclude],
        search_fields=[field for field in fields if field.lower() not in search_fields_exclude],
        list_filter=[field for field in fields if field.lower() not in list_filter_exclude],
    )

# 自动导入剩余model
for name, obj in inspect.getmembers(models.fta):
    try:
        if inspect.isclass(obj) and name not in [model_admin[0] for model_admin in model_admins]:
            admin.site.register(getattr(models, name))
    except Exception:
        pass
