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

import yaml
from django import forms
from django.contrib import admin

from metadata import models
from metadata.models.entity_relation import NAMESPACE_ALL


class YamlJsonField(forms.CharField):
    """
    自定义表单字段：同时接受 YAML 和 JSON 输入，存储为 JSON。
    展示时将 JSON 转为 YAML 格式，方便阅读和编辑。
    """

    widget = forms.Textarea(attrs={"rows": 10, "cols": 80, "style": "font-family: monospace;"})

    def __init__(self, *args, **kwargs):
        self.json_default = kwargs.pop("json_default", None)
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        """展示时将数据转为缩进 JSON 格式（避免 YAML 缩进在浏览器中被转为 &nbsp; 的问题）"""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except Exception:
            return str(value)

    def clean(self, value):
        value = super().clean(value)
        if not value or not value.strip():
            if self.json_default is not None:
                return self.json_default()
            return value

        # 浏览器提交时可能将空格转为 HTML 实体 &nbsp; 或 Unicode U+00A0
        # 统一替换为普通空格后再解析
        value = value.replace("&nbsp;", " ").replace("\u00a0", " ")

        # 先尝试 YAML 解析（YAML 是 JSON 的超集，所以 JSON 也能被正确解析）
        try:
            parsed = yaml.safe_load(value)
        except yaml.YAMLError:
            pass
        else:
            if isinstance(parsed, (dict, list)):
                return parsed
            # 标量值（如纯字符串/数字），尝试 JSON 解析
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass

        raise forms.ValidationError("输入格式无效，请使用 YAML 或 JSON 格式。")


class ResourceDefinitionForm(forms.ModelForm):
    labels = YamlJsonField(label="资源标签", required=False, json_default=dict)
    fields_def = YamlJsonField(label="字段定义列表", required=False, json_default=list)

    class Meta:
        model = models.ResourceDefinition
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 将 model 的 fields 字段映射到 fields_def 表单字段（避免与 Meta.fields 冲突）
        if self.instance and self.instance.pk:
            self.initial["fields_def"] = self.instance.fields

    def clean(self):
        cleaned = super().clean()
        cleaned["fields"] = cleaned.pop("fields_def", [])
        return cleaned

    def save(self, commit=True):
        self.instance.fields = self.cleaned_data.get("fields", [])
        return super().save(commit=commit)


class RelationDefinitionForm(forms.ModelForm):
    labels = YamlJsonField(label="资源标签", required=False, json_default=dict)

    class Meta:
        model = models.RelationDefinition
        fields = "__all__"

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


class EntityDefinitionAdminMixin:
    """
    Mixin for ResourceDefinition/RelationDefinition Admin：
    - 保存时若 spec 或 labels 发生变化，自动递增 generation
    - 保存后同步更新 Redis 缓存
    """

    @admin.display(description="命名空间")
    def namespace_display(self, obj):
        """库中空字符串与业务上的全局命名空间 NAMESPACE_ALL 一致，列表中统一展示为 __all__。"""
        return obj.namespace if obj.namespace else NAMESPACE_ALL

    def save_model(self, request, obj, form, change):
        if change:
            # 从数据库取当前值进行 spec 对比，有变化则递增 generation
            try:
                old = obj.__class__.objects.get(pk=obj.pk)
                if obj.get_spec() != old.get_spec() or obj.labels != old.labels:
                    obj.generation += 1
            except obj.__class__.DoesNotExist:
                pass
        super().save_model(request, obj, form, change)
        # 保存后同步到 Redis（复用 EntityHandler._rebuild_redis_cache）
        try:
            from metadata.resources.entity_relation import EntityHandler

            handler = EntityHandler(obj.__class__)
            handler._rebuild_redis_cache(obj)
        except Exception:
            pass


class ResourceDefinitionAdmin(EntityDefinitionAdminMixin, admin.ModelAdmin):
    form = ResourceDefinitionForm
    list_display = ("namespace_display", "name", "uid", "generation", "labels", "create_time", "update_time")
    search_fields = ("namespace", "name")
    list_filter = ("namespace",)
    exclude = ("fields",)  # 使用 fields_def 替代，避免字段名冲突


class RelationDefinitionAdmin(EntityDefinitionAdminMixin, admin.ModelAdmin):
    form = RelationDefinitionForm
    list_display = (
        "namespace_display",
        "name",
        "from_resource",
        "to_resource",
        "category",
        "is_directional",
        "is_belongs_to",
        "uid",
        "generation",
        "create_time",
        "update_time",
    )
    search_fields = ("namespace", "name", "from_resource", "to_resource")
    list_filter = ("namespace", "category", "is_directional", "is_belongs_to")


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
admin.site.register(models.ResourceDefinition, ResourceDefinitionAdmin)
admin.site.register(models.RelationDefinition, RelationDefinitionAdmin)
