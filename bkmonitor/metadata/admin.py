"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.contrib import admin

from metadata import models

# Register your models here.


# influxdb 路由配置信息
class InfluxdbClusterAdmin(admin.ModelAdmin):
    search_fields = ("host_name", "cluster_name")
    list_filter = ("host_name", "cluster_name")
    list_display = ("host_name", "cluster_name")


class InfluxdbHostAdmin(admin.ModelAdmin):
    search_fields = ("host_name", "domain_name")
    list_filter = ("host_name", "domain_name")
    list_display = ("host_name", "domain_name", "port", "description", "status", "backup_rate_limit")


class InfluxdbTagAdmin(admin.ModelAdmin):
    search_fields = ("database", "measurement", "cluster_name")
    list_display = ("database", "measurement", "cluster_name", "tag_name", "tag_value", "host_list")


class InfluxDBStorageAdmin(admin.ModelAdmin):
    search_fields = ("table_id", "database", "real_table_name")
    list_display = (
        "table_id",
        "database",
        "real_table_name",
        "proxy_cluster_name",
        "storage_cluster_id",
        "partition_tag",
        "influxdb_proxy_storage_id",
    )
    list_filter = ("storage_cluster_id", "influxdb_proxy_storage_id", "proxy_cluster_name")


class KafkaStorageAdmin(admin.ModelAdmin):
    search_fields = (
        "table_id",
        "topic",
    )
    list_display = ("table_id", "topic", "partition", "storage_cluster_id")
    list_filter = ("storage_cluster_id",)


class RedisStorageAdmin(admin.ModelAdmin):
    search_fields = ("table_id", "key")
    list_display = ("table_id", "command", "key", "storage_cluster_id")
    list_filter = ("storage_cluster_id", "command")


class BkDataStorageAdmin(admin.ModelAdmin):
    list_display = ("table_id", "raw_data_id", "etl_json_config", "bk_data_result_table_id")
    search_fields = ("table_id", "bk_data_result_table_id")


class CustomReportSubscriptionAdmin(admin.ModelAdmin):
    search_fields = ("bk_biz_id", "subscription_id", "bk_data_id")
    list_display = ("bk_biz_id", "subscription_id", "bk_data_id", "config")


class PingServerSubscriptionConfigAdmin(admin.ModelAdmin):
    search_fields = ("subscription_id", "ip", "bk_cloud_id")
    list_display = ("subscription_id", "ip", "bk_cloud_id")


class DataSourceAdmin(admin.ModelAdmin):
    search_fields = ("bk_data_id", "data_name")
    list_display = ("bk_data_id", "data_name", "transfer_cluster_id")


class ESStorageAdmin(admin.ModelAdmin):
    search_fields = ("table_id",)
    list_display = (
        "table_id",
        "slice_size",
        "slice_gap",
        "retention",
        "index_settings",
        "mapping_settings",
        "storage_cluster_id",
    )


class EventGroupAdmin(admin.ModelAdmin):
    list_display = (
        "event_group_id",
        "event_group_name",
        "bk_data_id",
        "bk_biz_id",
        "table_id",
        "last_modify_user",
        "last_modify_time",
    )
    search_fields = ("event_group_id", "event_group_name", "bk_data_id", "table_id")
    list_filter = ("bk_biz_id",)


class TimeSeriesGroupAdmin(admin.ModelAdmin):
    list_display = (
        "time_series_group_id",
        "time_series_group_name",
        "bk_data_id",
        "bk_biz_id",
        "table_id",
        "last_modify_user",
        "last_modify_time",
    )
    search_fields = ("time_series_group_id", "time_series_group_name", "bk_data_id", "table_id")
    list_filter = ("bk_biz_id",)


class TimeSeriesMetricAdmin(admin.ModelAdmin):
    list_display = ("group_id", "table_id", "scope_id", "field_name", "field_scope", "last_modify_time", "create_time")
    search_fields = ("group_id", "field_name", "field_scope", "last_modify_time", "create_time")
    list_filter = ("group_id", "field_name", "field_scope", "table_id")


class TimeSeriesScopeAdmin(admin.ModelAdmin):
    list_display = ("id", "group_id", "scope_name", "auto_rules", "last_modify_time")
    search_fields = ("group_id", "scope_name")
    list_filter = ("group_id", "scope_name")


class ResultTableAdmin(admin.ModelAdmin):
    list_display = ("table_id", "table_name_zh", "bk_biz_id", "label", "last_modify_user", "last_modify_time")
    search_fields = ("table_id", "table_name_zh", "bk_biz_id")
    list_filter = ("bk_biz_id",)


class ResultTableFieldAdmin(admin.ModelAdmin):
    list_display = ("table_id", "field_name", "field_type", "tag", "description", "creator", "create_time")
    search_fields = ("table_id", "field_name")


class ResultTableOptionAdmin(admin.ModelAdmin):
    list_display = ("table_id", "name", "value_type", "value", "creator", "create_time")
    search_fields = ("table_id", "name")


class ClusterInfoAdmin(admin.ModelAdmin):
    list_display = (
        "cluster_id",
        "cluster_name",
        "cluster_type",
        "registered_system",
        "is_register_to_gse",
        "gse_stream_to_id",
        "last_modify_user",
        "last_modify_time",
    )
    search_fields = ("cluster_name", "cluster_type", "registered_system")
    list_filter = ("cluster_type", "registered_system")


class SpaceRelatedStorageInfoAdmin(admin.ModelAdmin):
    list_display = ("space_type_id", "space_id", "storage_type", "cluster_id")
    search_fields = ("cluster_id", "space_id")
    list_filter = ("cluster_id", "storage_type")


class KafkaTopicInfoAdmin(admin.ModelAdmin):
    list_display = ("bk_data_id", "topic", "partition")
    search_fields = ("topic",)


class DataSourceOptionAdmin(admin.ModelAdmin):
    list_display = ("bk_data_id", "name", "value_type", "value", "creator", "create_time")
    search_fields = ("bk_data_id", "name")


class DataSourceResultTableAdmin(admin.ModelAdmin):
    list_display = ("bk_data_id", "table_id", "creator", "create_time")
    search_fields = ("table_id",)


class ReplaceConfigAdmin(admin.ModelAdmin):
    list_display = ("rule_name", "is_common", "replace_type", "source_name", "target_name")
    search_fields = ("rule_name", "source_name", "target_name")


class InfluxDBProxyStorageAdmin(admin.ModelAdmin):
    list_display = ("id", "proxy_cluster_id", "service_name", "instance_cluster_name", "is_default")
    search_fields = ("id", "proxy_cluster_id", "service_name", "instance_cluster_name")
    list_filter = ("id", "service_name", "instance_cluster_name")


class AccessVMRecordAdmin(admin.ModelAdmin):
    list_display = ("data_type", "result_table_id", "storage_cluster_id")
    search_fields = ("result_table_id", "storage_cluster_id")
    list_filter = ("data_type",)


class BCSClusterInfoAdmin(admin.ModelAdmin):
    list_display = ("cluster_id", "bk_biz_id", "status", "K8sMetricDataID", "CustomMetricDataID", "K8sEventDataID")
    search_fields = ("cluster_id", "bk_biz_id")
    list_filter = ("cluster_id", "bk_biz_id")


class DataLinkAdmin(admin.ModelAdmin):
    list_display = ("data_link_name", "data_link_strategy", "create_time")
    search_fields = ("data_link_name", "data_link_strategy", "namespace")
    list_filter = ("data_link_strategy", "namespace")


class BkBaseResultTableAdmin(admin.ModelAdmin):
    list_display = ("data_link_name", "bkbase_data_name", "storage_type", "monitor_table_id", "status")
    search_fields = ("data_link_name", "monitor_table_id")
    list_filter = ("storage_type", "status")


class StorageClusterRecordAdmin(admin.ModelAdmin):
    list_display = ("table_id", "cluster_id", "is_deleted", "is_current")
    search_fields = ("table_id", "cluster_id")
    list_filter = ("table_id", "cluster_id")


class BkAppSpaceRecordAdmin(admin.ModelAdmin):
    list_display = ("bk_app_code", "space_uid", "is_enable", "creator", "create_time", "updater", "update_time")
    search_fields = ("bk_app_code", "space_uid")
    list_filter = ("bk_app_code", "space_uid")


admin.site.register(models.InfluxDBClusterInfo, InfluxdbClusterAdmin)
admin.site.register(models.InfluxDBHostInfo, InfluxdbHostAdmin)
admin.site.register(models.InfluxDBStorage, InfluxDBStorageAdmin)
admin.site.register(models.KafkaStorage, KafkaStorageAdmin)
admin.site.register(models.BkDataStorage, BkDataStorageAdmin)
admin.site.register(models.RedisStorage, RedisStorageAdmin)
admin.site.register(models.ESStorage, ESStorageAdmin)
admin.site.register(models.EventGroup, EventGroupAdmin)
admin.site.register(models.TimeSeriesGroup, TimeSeriesGroupAdmin)
admin.site.register(models.TimeSeriesMetric, TimeSeriesMetricAdmin)
admin.site.register(models.TimeSeriesScope, TimeSeriesScopeAdmin)
admin.site.register(models.CustomReportSubscription, CustomReportSubscriptionAdmin)
admin.site.register(models.PingServerSubscriptionConfig, PingServerSubscriptionConfigAdmin)
admin.site.register(models.ClusterInfo, ClusterInfoAdmin)
admin.site.register(models.SpaceRelatedStorageInfo, SpaceRelatedStorageInfoAdmin)
admin.site.register(models.KafkaTopicInfo, KafkaTopicInfoAdmin)
admin.site.register(models.DataSource, DataSourceAdmin)
admin.site.register(models.DataSourceOption, DataSourceOptionAdmin)
admin.site.register(models.DataSourceResultTable, DataSourceResultTableAdmin)
admin.site.register(models.InfluxDBTagInfo, InfluxdbTagAdmin)
admin.site.register(models.ResultTable, ResultTableAdmin)
admin.site.register(models.ResultTableField, ResultTableFieldAdmin)
admin.site.register(models.ResultTableOption, ResultTableOptionAdmin)
admin.site.register(models.ReplaceConfig, ReplaceConfigAdmin)
admin.site.register(models.InfluxDBProxyStorage, InfluxDBProxyStorageAdmin)
admin.site.register(models.AccessVMRecord, AccessVMRecordAdmin)
admin.site.register(models.BCSClusterInfo, BCSClusterInfoAdmin)
admin.site.register(models.DataLink, DataLinkAdmin)
admin.site.register(models.BkBaseResultTable, BkBaseResultTableAdmin)
admin.site.register(models.StorageClusterRecord, StorageClusterRecordAdmin)
admin.site.register(models.BkAppSpaceRecord, BkAppSpaceRecordAdmin)
