"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.utils.user import get_local_username, get_request_username
from core.drf_resource import CacheResource, Resource, api
from core.drf_resource.contrib.nested_api import KernelAPIResource


class MetaDataAPIGWResource(KernelAPIResource):
    base_url_statement = None
    base_url = (
        settings.NEW_MONITOR_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-monitor/{settings.APIGW_STAGE}/"
    )
    # 模块名
    module_name = "metadata_v3"

    @property
    def label(self):
        return self.__doc__


class MetadataBaseSerializer(serializers.Serializer):
    def validate(self, attrs):
        # 移除值为 None 的字段
        for field in list(attrs.keys()):
            if attrs[field] is None:
                del attrs[field]
        return attrs


class GetLabelResource(MetaDataAPIGWResource):
    """
    获取分类标签（一二级标签）
    """

    action = "/app/metadata/list_label/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        # 标签分类，source_label, type_label or result_table_label
        label_type = serializers.CharField(required=False, label="标签分类")
        # 标签层级, 层级从1开始计算, 该配置只在label_type为result_table时生效
        level = serializers.IntegerField(required=False, label="标签层级")
        include_admin_only = serializers.BooleanField(required=False, label="是否展示管理员可见标签")


class CreateDataIdResource(MetaDataAPIGWResource):
    """
    创建监控数据源
    """

    action = "/app/metadata/create_data_id/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        data_name = serializers.CharField(required=True)
        etl_config = serializers.CharField(required=True, allow_blank=True)
        operator = serializers.CharField(required=True)
        mq_cluster = serializers.IntegerField(required=False)
        data_description = serializers.CharField(required=False)
        is_custom_source = serializers.BooleanField(required=False, default=True)
        source_label = serializers.CharField(required=True)
        type_label = serializers.CharField(required=True)
        option = serializers.DictField(required=False)
        space_uid = serializers.CharField(required=False)
        bk_biz_id = serializers.IntegerField(required=False)
        is_platform_data_id = serializers.BooleanField(required=False)


class CreateResultTableResource(MetaDataAPIGWResource):
    """
    创建监控结果表
    """

    action = "/app/metadata/create_result_table/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(required=True)
        table_id = serializers.CharField(required=True)
        table_name_zh = serializers.CharField(required=True)
        is_custom_table = serializers.BooleanField(required=True)
        schema_type = serializers.ChoiceField(required=True, choices=["free", "fixed"])
        operator = serializers.CharField(required=True)
        default_storage = serializers.ChoiceField(required=True, choices=["influxdb", "kafka"])
        default_storage_config = serializers.DictField(required=False)
        field_list = serializers.ListField(required=False)
        bk_biz_id = serializers.IntegerField(required=False)
        label = serializers.CharField(required=False, allow_blank=True)
        external_storage = serializers.DictField(required=False)
        option = serializers.DictField(required=False)
        is_time_field_only = serializers.BooleanField(required=False, label="是否仅需要提供时间默认字段", default=False)
        time_option = serializers.DictField(required=False, label="时间字段选项配置", allow_null=True)
        data_label = serializers.CharField(required=False, label="数据标签")


class ListResultTableResource(MetaDataAPIGWResource):
    """
    查询监控结果表
    """

    action = "/app/metadata/list_result_table/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        datasource_type = serializers.CharField(required=False, label="需要过滤的结果表类型，如 system")
        is_public_include = serializers.BooleanField(required=False, label="是否包含全业务结果表")
        page = serializers.IntegerField(required=False, label="页数", min_value=1)
        page_size = serializers.IntegerField(required=False, label="页长")
        with_option = serializers.BooleanField(required=False, label="是否包含option字段")

        def validate_is_public_include(self, val):
            return 1 if val else 0


class ModifyResultTableResource(MetaDataAPIGWResource):
    """
    修改监控结果表
    """

    action = "/app/metadata/modify_result_table/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True)
        operator = serializers.CharField(required=True)
        field_list = serializers.ListField(required=False)
        table_name_zh = serializers.CharField(required=False)
        default_storage = serializers.ChoiceField(required=False, choices=["influxdb", "kafka"])
        label = serializers.CharField(required=True)
        option = serializers.DictField(required=False)
        is_time_field_only = serializers.BooleanField(required=False, label="默认字段仅有time")
        external_storage = serializers.DictField(required=False, label="额外存储")
        is_enable = serializers.BooleanField(required=False, label="是否启用结果表")
        time_option = serializers.DictField(required=False, label="时间字段选项配置", allow_null=True)
        is_reserved_check = serializers.BooleanField(required=False, label="是否进行保留字检查")
        data_label = serializers.CharField(required=False, label="数据标签")


class GetDataIdResource(MetaDataAPIGWResource):
    """
    获取监控数据源具体信息
    """

    backend_cache_type = CacheType.DB_CACHE

    action = "/app/metadata/get_data_id/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(required=False)
        data_name = serializers.CharField(required=False)
        with_rt_info = serializers.BooleanField(required=False, label="是否需要ResultTable信息")


class QueryDataSourceBySpaceUidResource(MetaDataAPIGWResource):
    """
    根据space_uid查询data_source
    """

    action = "/app/metadata/query_data_source_by_space_uid/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        space_uid_list = serializers.ListField(required=True, label="数据源所属空间uid列表")
        is_platform_data_id = serializers.BooleanField(required=False, label="是否为平台级 ID", default=True)


class GetResultTableResource(MetaDataAPIGWResource):
    """
    获取监控结果表具体信息
    """

    action = "/app/metadata/get_result_table/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True)


class GetResultTableStorageResource(MetaDataAPIGWResource):
    """
    获取监控结果表具体信息
    """

    action = "/app/metadata/get_result_table_storage/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        result_table_list = serializers.CharField(required=True)
        storage_type = serializers.CharField(required=True)


class GetTsDataResource(MetaDataAPIGWResource):
    """
    数据查询
    """

    action = "/app/data_query/get_ts_data/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        sql = serializers.CharField(required=True)


class GetEsDataResource(MetaDataAPIGWResource):
    """
    ES数据查询
    """

    action = "/app/data_query/get_es_data/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True, label="结果表ID")
        query_body = serializers.DictField(required=True, label="查询内容")
        use_full_index_names = serializers.BooleanField(required=False, label="是否使用索引全名进行检索", default=False)


class ModifyDataIdResource(MetaDataAPIGWResource):
    """
    修改dataid和dataname的关系
    """

    action = "/app/metadata/modify_data_id/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        operator = serializers.CharField(required=True, label="操作者")
        data_name = serializers.CharField(required=False, label="数据源名称")
        data_id = serializers.IntegerField(required=True, label="数据源ID")
        data_description = serializers.CharField(required=False, label="数据源描述")
        option = serializers.DictField(required=False, label="数据源配置项")
        is_enable = serializers.BooleanField(required=False, label="是否启用数据源")


class CreateResultTableMetricSplitResource(MetaDataAPIGWResource):
    """
    创建一个结果表CMDB拆分
    """

    action = "/app/metadata/create_result_table_metric_split/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True, label="结果表ID")
        cmdb_level = serializers.CharField(required=True, label="MDB拆分层级名")
        operator = serializers.CharField(required=True, label="操作者")


class ListMonitorResultTableResource(Resource):
    # todo to being legacy
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        datasource_type = serializers.CharField(required=False, label="需要过滤的结果表类型，如 system")
        is_public_include = serializers.BooleanField(required=False, label="是否包含全业务结果表")
        with_option = serializers.BooleanField(required=False, label="是否包含option字段")

    def perform_request(self, validated_request_data):
        result_data = batch_request(api.metadata.list_result_table, validated_request_data, limit=1000, app="metadata")
        validated_data = []
        for table in result_data:
            # 对非法table_id的数据进行过滤
            if len(table["table_id"].split(".")) != 2:
                continue

            for field in table["field_list"]:
                if field["tag"] != "metric":
                    continue

                if not field.get("alias_name"):
                    field["alias_name"] = field["description"]

                field["unit_conversion"] = 1.0

            validated_data.append(table)
        return validated_data


class CreateEventGroupResource(MetaDataAPIGWResource):
    """
    创建事件分组
    """

    action = "/app/metadata/create_event_group/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        operator = serializers.CharField(allow_blank=True, label="操作者")
        bk_data_id = serializers.IntegerField(label="数据ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        event_group_name = serializers.CharField(label="事件分组名")
        label = serializers.CharField(label="分组标签")
        event_info_list = serializers.ListField(required=False, label="事件列表")
        data_label = serializers.CharField(required=False, label="数据标签")


class ModifyEventGroupResource(MetaDataAPIGWResource):
    """
    修改事件分组
    """

    action = "/app/metadata/modify_event_group/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        operator = serializers.CharField(allow_blank=True, label="操作者")
        event_group_id = serializers.IntegerField(label="事件分组ID")
        event_group_name = serializers.CharField(required=False, label="事件分组名")
        label = serializers.CharField(required=False, label="分组标签")
        event_info_list = serializers.ListField(required=False, label="事件列表", allow_empty=True)
        is_enable = serializers.BooleanField(required=False, label="是否启用")
        data_label = serializers.CharField(required=False, label="数据标签")


class DeleteEventGroupResource(MetaDataAPIGWResource):
    """
    删除事件分组
    """

    action = "/app/metadata/delete_event_group/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        operator = serializers.CharField(allow_blank=True, label="操作者")
        event_group_id = serializers.IntegerField(label="事件分组ID")


class GetEventGroupResource(MetaDataAPIGWResource):
    """
    获取事件分组
    """

    action = "/app/metadata/get_event_group/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        event_group_id = serializers.IntegerField(label="事件分组ID")
        with_result_table_info = serializers.BooleanField(label="是否返回数据源信息", required=False)
        need_refresh = serializers.BooleanField(required=False, label="是否需要实时刷新", default=False)
        event_infos_limit = serializers.IntegerField(required=False, default=None, label="事件信息列表上限")


class SingleQueryEventGroupResource(MetaDataAPIGWResource):
    """
    查询事件分组
    """

    action = "/app/metadata/query_event_group/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        label = serializers.CharField(required=False, label="分组标签")
        event_group_name = serializers.CharField(required=False, label="分组名称")
        bk_data_ids = serializers.ListField(
            required=False, label="数据源ID列表", child=serializers.IntegerField(label="数据源ID")
        )
        page = serializers.IntegerField(required=False, label="页数", min_value=1)
        page_size = serializers.IntegerField(required=False, label="页长")


class QueryEventGroupResource(CacheResource):
    """
    批量查询事件分组
    """

    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        label = serializers.CharField(required=False, label="分组标签")
        event_group_name = serializers.CharField(required=False, label="分组名称")
        bk_data_ids = serializers.ListField(
            required=False, label="数据源ID列表", child=serializers.IntegerField(label="数据源ID")
        )

    def perform_request(self, validated_request_data):
        return batch_request(api.metadata.single_query_event_group, validated_request_data, limit=500, app="metadata")


class CreateTimeSeriesGroupResource(MetaDataAPIGWResource):
    """
    创建自定义时序分组
    """

    action = "/app/metadata/create_time_series_group/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        operator = serializers.CharField(allow_blank=True, label="操作者")
        bk_data_id = serializers.IntegerField(label="数据ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        time_series_group_name = serializers.CharField(label="自定义时序分组名")
        label = serializers.CharField(label="分组标签")
        metric_info_list = serializers.ListField(required=False, label="Metric列表")
        table_id = serializers.CharField(required=False, label="结果表id")
        is_split_measurement = serializers.BooleanField(required=False, label="是否启动自动分表逻辑", default=True)
        additional_options = serializers.DictField(required=False, label="附带创建的ResultTableOption")
        data_label = serializers.CharField(required=False, label="数据标签")
        metric_group_dimensions = serializers.JSONField(required=False, label="指标分组的维度key配置")


class ModifyTimeSeriesGroupResource(MetaDataAPIGWResource):
    """
    修改自定义时序分组
    """

    action = "/app/metadata/modify_time_series_group/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        operator = serializers.CharField(allow_blank=True, label="操作者")
        time_series_group_id = serializers.IntegerField(label="自定义时序分组ID")
        time_series_group_name = serializers.CharField(required=False, label="自定义时序分组名")
        label = serializers.CharField(required=False, label="分组标签")
        field_list = serializers.ListField(required=False, label="自定义时序列表", allow_empty=True)
        is_enable = serializers.BooleanField(required=False, label="是否启用")
        enable_field_black_list = serializers.BooleanField(required=False, label="黑名单的启用状态")
        metric_info_list = serializers.ListField(required=False, label="metric信息")
        data_label = serializers.CharField(required=False, label="数据标签")


class DeleteTimeSeriesGroupResource(MetaDataAPIGWResource):
    """
    删除自定义时序分组
    """

    action = "/app/metadata/delete_time_series_group/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        operator = serializers.CharField(allow_blank=True, label="操作者")
        time_series_group_id = serializers.IntegerField(label="自定义时序分组ID")


class GetTimeSeriesGroupResource(MetaDataAPIGWResource):
    """
    获取自定义时序分组
    """

    action = "/app/metadata/get_time_series_group/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(label="自定义时序分组ID")
        with_result_table_info = serializers.BooleanField(label="是否返回数据源信息", required=False)


class SingleQueryTimeSeriesGroupResource(MetaDataAPIGWResource):
    """
    查询自定义时序分组
    """

    action = "/app/metadata/query_time_series_group/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        label = serializers.CharField(required=False, label="分组标签")
        time_series_group_name = serializers.CharField(required=False, label="分组名称")
        page = serializers.IntegerField(required=False, label="页数", min_value=1)
        page_size = serializers.IntegerField(required=False, label="页长")


class QueryTimeSeriesGroupResource(CacheResource):
    """
    批量查询自定义时序分组
    """

    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        label = serializers.CharField(required=False, label="分组标签")
        time_series_group_name = serializers.CharField(required=False, label="分组名称")

    def perform_request(self, validated_request_data):
        return batch_request(
            api.metadata.single_query_time_series_group, validated_request_data, limit=500, app="metadata"
        )


class CreateOrUpdateTimeSeriesMetricResource(MetaDataAPIGWResource):
    """
    批量创建或更新自定义时序指标
    """

    action = "/app/metadata/create_or_update_time_series_metric/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class MetricSerializer(serializers.Serializer):
            """单个指标的序列化器"""

            field_id = serializers.IntegerField(required=False, label="字段ID")
            field_name = serializers.CharField(required=False, label="指标字段名称", max_length=255)
            field_scope = serializers.CharField(required=False, label="指标数据分组", max_length=255)
            tag_list = serializers.ListField(
                required=False, label="Tag列表", child=serializers.CharField(), allow_null=True
            )
            field_config = serializers.DictField(required=False, label="字段其他配置", allow_null=True)
            label = serializers.CharField(required=False, label="指标监控对象", max_length=255, allow_null=True)
            scope_id = serializers.IntegerField(required=True, label="指标分组ID")

        group_id = serializers.IntegerField(required=True, label="自定义时序数据源ID")
        metrics = serializers.ListField(
            required=True,
            label="批量指标列表",
            child=MetricSerializer(),
            allow_empty=False,
        )


class CreateOrUpdateTimeSeriesScopeResource(MetaDataAPIGWResource):
    """
    批量创建或更新自定义时序指标分组
    """

    action = "/app/metadata/create_or_update_time_series_scope/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        group_id = serializers.IntegerField(required=True, label="自定义时序数据源ID")

        class ScopeSerializer(serializers.Serializer):
            scope_id = serializers.IntegerField(required=False, label="指标分组ID")
            scope_name = serializers.CharField(required=False, label="指标分组名", max_length=255)
            dimension_config = serializers.DictField(required=False, allow_null=True, label="分组下的维度配置")
            auto_rules = serializers.ListField(required=False, label="自动分组的匹配规则列表")

        scopes = serializers.ListField(
            required=True, child=ScopeSerializer(), label="批量创建或更新的分组列表", min_length=1
        )


class DeleteTimeSeriesScopeResource(MetaDataAPIGWResource):
    """
    批量删除自定义时序指标分组
    """

    action = "/app/metadata/delete_time_series_scope/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        group_id = serializers.IntegerField(required=True, label="自定义时序数据源ID")

        class ScopeSerializer(serializers.Serializer):
            scope_name = serializers.CharField(required=True, label="指标分组名", max_length=255)

        scopes = serializers.ListField(required=True, child=ScopeSerializer(), label="批量删除的分组列表", min_length=1)


class QueryTimeSeriesScopeResource(MetaDataAPIGWResource):
    """
    查询自定义时序指标分组列表
    """

    action = "/app/metadata/query_time_series_scope/"
    method = "POST"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        group_id = serializers.IntegerField(required=True, label="自定义时序数据源ID")
        scope_ids = serializers.ListField(
            child=serializers.IntegerField(), required=False, label="指标分组ID列表", allow_empty=True
        )
        scope_name = serializers.CharField(required=False, label="指标分组名称")
        include_metrics = serializers.BooleanField(required=False, default=False, label="是否返回指标数据")


class QueryTimeSeriesMetricResource(MetaDataAPIGWResource):
    """
    查询自定义时序指标列表
    """

    action = "/app/metadata/query_time_series_metric/"
    method = "POST"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        class QueryTimeSeriesMetricConditionSerializer(serializers.Serializer):
            """搜索条件序列化器"""

            key = serializers.ChoiceField(
                choices=[
                    "name",
                    "field_config_alias",
                    "field_config_unit",
                    "field_config_aggregate_method",
                    "field_config_hidden",
                    "field_config_disabled",
                    "scope_id",
                    "field_id",
                ],
                required=True,
                label="搜索字段",
            )
            values = serializers.ListField(
                child=serializers.CharField(),
                required=True,
                label="搜索值列表（多个值用OR连接）",
                min_length=1,
            )
            search_type = serializers.ChoiceField(
                choices=["regex", "fuzzy", "exact"],
                required=False,
                default="fuzzy",
                label="搜索类型：regex-正则表达式，fuzzy-模糊搜索，exact-精确匹配（仅对name字段有效，其他字段默认为exact）",
            )

        bk_tenant_id = TenantIdField(label="租户ID")
        group_id = serializers.IntegerField(required=True, label="自定义时序数据源ID")
        page = serializers.IntegerField(default=1, required=False, label="页数", min_value=1)
        page_size = serializers.IntegerField(default=10, required=False, label="页长", min_value=1, max_value=1000)
        conditions = serializers.ListField(
            child=QueryTimeSeriesMetricConditionSerializer(),
            required=False,
            label="搜索条件列表，同一字段的多个值用OR，不同字段之间用AND",
            allow_empty=True,
        )
        order_by = serializers.ChoiceField(
            choices=["name", "update_time", "-name", "-update_time"],
            required=False,
            default="-update_time",
            label="排序字段：name-按名称升序，update_time-按更新时间升序，-name-按名称降序，-update_time-按更新时间降序",
        )


class QueryTagValuesResource(MetaDataAPIGWResource):
    """
    查询指定tag/dimension valuestag/dimension values
    查询自定义时序分组
    """

    action = "/app/metadata/query_tag_values/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=False, label="结果表ID")
        tag_name = serializers.CharField(required=False, label="TAG名称")


class QueryClusterInfoResource(MetaDataAPIGWResource):
    """
    查询集群信息
    """

    action = "/app/metadata/get_cluster_info/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(MetadataBaseSerializer):
        cluster_id = serializers.IntegerField(required=False, label="存储集群ID", default=None)
        cluster_name = serializers.CharField(required=False, label="存储集群名", default=None)
        cluster_type = serializers.CharField(required=False, label="存储集群类型", default=None)
        is_plain_text = serializers.BooleanField(required=False, label="是否需要明文显示登陆信息", default=False)
        registered_system = serializers.CharField(required=False, label="来源系统名称", default="")


class AccessBkDataByResultTable(MetaDataAPIGWResource):
    """
    创建降采样dataflow
    """

    action = "/app/metadata/access_bk_data_by_result_table/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True, label="结果表ID")  # eg: system.load
        is_access_now = serializers.BooleanField(default=False, label="是否立即接入")


class IsDataLabelExistResource(MetaDataAPIGWResource):
    """
    判断结果表中是否存在指定data_label
    """

    action = "/app/metadata/is_data_label_exist/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(required=False, default=None)
        data_label = serializers.CharField(required=True, label="数据标签")


class CreateDownSampleDataFlow(MetaDataAPIGWResource):
    """
    创建降采样dataflow
    """

    action = "/app/metadata/create_down_sample_data_flow/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        agg_interval = serializers.IntegerField(required=True)
        table_id = serializers.CharField(required=True, label="结果表ID")  # eg: system.load


class FullCmdbNodeInfo(MetaDataAPIGWResource):
    """
    补充CMDB节点信息（需要保证表中有bk_target_ip、bk_target_cloud_id两个字段）
    """

    action = "/app/metadata/full_cmdb_node_info/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True, label="结果表ID")  # eg: system.load


class CheckOrCreateKafkaStorageResource(MetaDataAPIGWResource):
    """
    检查对应结果表的kafka存储是否存在，不存在则创建
    """

    action = "/app/metadata/check_or_create_kafka_storage/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        table_ids = serializers.ListField(required=True, label="结果表IDs")


class RegisterBCSClusterResource(MetaDataAPIGWResource):
    """
    将BCS集群信息注册到metadata，并进行一系列初始化操作
    """

    action = "/app/metadata/register_bcs_cluster/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务id")
        cluster_id = serializers.CharField(required=True, label="bcs集群id")
        project_id = serializers.CharField(required=True, label="bcs项目id")
        creator = serializers.CharField(required=True, label="操作人")
        domain_name = serializers.CharField(required=False, label="bcs域名")
        port = serializers.IntegerField(required=False, label="bcs端口")
        api_key_type = serializers.CharField(required=False, label="api密钥类型")
        api_key_prefix = serializers.CharField(required=False, label="api密钥前缀")
        is_skip_ssl_verify = serializers.BooleanField(required=False, label="是否跳过ssl认证")
        transfer_cluster_id = serializers.CharField(required=False, label="transfer集群id")


class ModifyBCSResourceInfoResource(MetaDataAPIGWResource):
    """
    修改bcs的resource内容，通常为调整dataid
    """

    action = "/app/metadata/modify_bcs_resource_info/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.CharField(required=True, label="bcs集群id")
        resource_type = serializers.CharField(required=True, label="resource类型")
        resource_name = serializers.CharField(required=True, label="resource名称")
        data_id = serializers.IntegerField(required=True, label="修改后的目标dataid")


class ListBCSResourceInfoResource(MetaDataAPIGWResource):
    action = "/app/metadata/list_bcs_resource_info/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        cluster_ids = serializers.ListField(required=False, label="bcs集群id", default=[])
        resource_type = serializers.CharField(required=True, label="resource类型")


class ListBCSClusterInfoResource(MetaDataAPIGWResource):
    action = "/app/metadata/list_bcs_cluster_info/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        cluster_ids = serializers.ListField(label="集群ID", child=serializers.CharField(), required=False)


class QueryBCSMetricsResource(MetaDataAPIGWResource):
    action = "/app/metadata/query_bcs_metrics/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(required=False, label="业务ID", default=[], child=serializers.IntegerField())
        cluster_ids = serializers.ListField(required=False, label="BCS集群ID", default=[])
        dimension_name = serializers.CharField(required=False, label="指标名称", default="")
        dimension_value = serializers.CharField(required=False, label="指标取值", default="")


class EsRouteResource(MetaDataAPIGWResource):
    action = "/app/metadata/es_route/"
    method = "POST"


class KafkaTailResource(MetaDataAPIGWResource):
    action = "/app/metadata/kafka_tail/"
    method = "GET"


class GetTimeSeriesMetricsResource(MetaDataAPIGWResource):
    action = "/app/metadata/get_time_series_metrics/"
    method = "GET"


class ListSpaceTypesResource(MetaDataAPIGWResource):
    action = "/app/metadata/list_space_types/"
    method = "GET"
    cache_type = CacheType.METADATA

    def cache_write_trigger(self, res):
        return bool(res)


class ListSpacesResource(MetaDataAPIGWResource):
    action = "/app/metadata/list_spaces/"
    method = "GET"
    cache_type = CacheType.METADATA

    def cache_write_trigger(self, res):
        return bool(res)


class GetSpaceDetailResource(MetaDataAPIGWResource):
    action = "/app/metadata/get_space_detail/"
    method = "GET"
    cache_type = CacheType.METADATA


class GetClustersBySpaceUidResource(MetaDataAPIGWResource):
    action = "/app/metadata/get_clusters_by_space_uid/"
    method = "GET"
    cache_type = CacheType.METADATA


class UsernameSerializer(MetadataBaseSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("username"):
            username = get_request_username() or get_local_username()
            attrs["username"] = username
        if not attrs.get("username"):
            raise ValidationError("(username) This field is required")
        return attrs


class ListStickySpacesResource(MetaDataAPIGWResource):
    action = "/app/metadata/list_sticky_spaces/"
    method = "GET"

    class RequestSerializer(UsernameSerializer):
        pass


class StickSpaceResource(MetaDataAPIGWResource):
    action = "/app/metadata/stick_space/"
    method = "POST"

    class RequestSerializer(UsernameSerializer):
        action = serializers.CharField(label="置顶动作", default="on")
        space_uid = serializers.CharField(label="空间uid")
        username = serializers.CharField(label="用户名", required=True)


class CreateSpaceResource(MetaDataAPIGWResource):
    action = "/app/metadata/create_space/"
    method = "POST"

    class RequestSerializer(UsernameSerializer):
        space_name = serializers.CharField(label="空间中文名称")
        space_type_id = serializers.CharField(label="空间类型", required=False, default="default")
        space_id = serializers.CharField(label="空间 ID", default="")
        username = serializers.CharField(label="创建者")

        def validate(self, attrs):
            attrs = super().validate(attrs)
            attrs["creator"] = attrs["username"]
            return attrs


class QueryDataSourceResource(MetaDataAPIGWResource):
    """
    查询数据源
    """

    action = "/app/metadata/query_data_source/"
    method = "GET"
    backend_cache_type = CacheType.METADATA

    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(required=False, label="数据源ID", default=None)
        data_name = serializers.CharField(required=False, label="数据源名称", default=None)
        with_rt_info = serializers.BooleanField(required=False, label="是否需要ResultTable信息", default=True)


class ListClustersResource(MetaDataAPIGWResource):
    action = "/app/metadata/list_clusters/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        cluster_type = serializers.CharField(label="集群类型", required=False, default="all")
        page_size = serializers.IntegerField(default=10, label="每页的条数")
        page = serializers.IntegerField(default=1, min_value=1, label="页数")


class GetStorageClusterDetailResource(MetaDataAPIGWResource):
    action = "/app/metadata/get_storage_cluster_detail/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.CharField(label="集群 ID", required=True)


class RegisterClusterResource(MetaDataAPIGWResource):
    action = "/app/metadata/register_cluster/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        cluster_name = serializers.CharField(label="集群名称")
        cluster_type = serializers.CharField(label="集群类型")
        domain = serializers.CharField(label="集群域名")
        port = serializers.IntegerField(label="集群端口")
        registered_system = serializers.CharField(label="注册来源系统")
        operator = serializers.CharField(label="创建者")
        description = serializers.CharField(label="描述", default="", allow_blank=True)
        username = serializers.CharField(label="访问集群的用户名", default="", allow_blank=True)
        password = serializers.CharField(label="访问集群的密码", default="", allow_blank=True)
        version = serializers.CharField(label="集群版本", default="", allow_blank=True)
        schema = serializers.CharField(label="访问协议", default="", allow_blank=True)
        is_ssl_verify = serializers.BooleanField(label="是否 ssl 验证", default=False)
        label = serializers.CharField(label="标签", default="", allow_blank=True)


class UpdateRegisteredClusterResource(MetaDataAPIGWResource):
    action = "/app/metadata/update_registered_cluster/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.IntegerField(label="集群 ID")
        operator = serializers.CharField(label="创建者")
        description = serializers.CharField(label="描述", default="", allow_blank=True)
        username = serializers.CharField(label="访问集群的用户名", default="", allow_blank=True)
        password = serializers.CharField(label="访问集群的密码", default="", allow_blank=True)
        version = serializers.CharField(label="集群版本", default="", allow_blank=True)
        schema = serializers.CharField(label="访问协议", default="", allow_blank=True)
        is_ssl_verify = serializers.BooleanField(label="是否 ssl 验证", default=False)
        label = serializers.CharField(label="标签", default="", allow_blank=True)
        default_settings = serializers.JSONField(required=False, label="默认集群配置", default={})


class CustomTimeSeriesDetailResource(MetaDataAPIGWResource):
    action = "/app/custom_metric/detail/"
    method = "GET"

    ignore_error_msg_list = ["custom time series table not found"]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        model_only = serializers.BooleanField(required=False, default=False)
        empty_if_not_found = serializers.BooleanField(required=False, default=False)


class QueryResultTableStorageDetailResource(MetaDataAPIGWResource):
    action = "/app/metadata/query_result_table_storage_detail/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(required=False, label="数据源ID")
        table_id = serializers.CharField(required=False, label="结果表ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")


class GetDataLabelsMapResource(MetaDataAPIGWResource):
    action = "/app/metadata/get_data_labels_map/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.CharField(label="业务ID")
        table_or_labels = serializers.ListField(
            child=serializers.CharField(), label="结果表ID列表", default=[], min_length=1
        )
