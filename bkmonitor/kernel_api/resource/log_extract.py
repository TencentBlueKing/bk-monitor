"""日志提取 MCP 资源。"""

from rest_framework import serializers

from core.drf_resource import Resource, api


class SearchLogExtractHostsResource(Resource):
    """查询用户日志提取策略允许访问的主机。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        all_scope = serializers.BooleanField(required=False, default=False)
        scope_list = serializers.ListField(child=serializers.DictField(), required=False, default=list)
        node_list = serializers.ListField(child=serializers.DictField())
        search_condition = serializers.DictField(required=False)
        search_content = serializers.CharField(required=False, allow_blank=True)
        conditions = serializers.ListField(child=serializers.DictField(), required=False)
        start = serializers.IntegerField(required=False, default=0, min_value=0)
        page_size = serializers.IntegerField(required=False, default=-1, min_value=-1, max_value=500)

    def perform_request(self, validated_request_data):
        return api.log_search.query_log_extract_hosts(**validated_request_data)


class SearchLogExtractFilesResource(Resource):
    """查询用户日志提取策略允许访问的文件。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        ip_list = serializers.ListField(child=serializers.DictField(), min_length=1)
        path = serializers.CharField(required=True)
        is_search_child = serializers.BooleanField(required=True)
        time_range = serializers.CharField(required=True)
        start_time = serializers.CharField(required=False, allow_blank=True)
        end_time = serializers.CharField(required=False, allow_blank=True)

    def perform_request(self, validated_request_data):
        return api.log_search.list_log_extract_files(**validated_request_data)


class CreateLogExtractTaskResource(Resource):
    """创建异步日志提取任务。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        target_node_type = serializers.CharField(required=False)
        ip_list = serializers.ListField(child=serializers.DictField(), required=False)
        target_nodes = serializers.ListField(child=serializers.DictField(), required=False)
        file_path = serializers.ListField(child=serializers.CharField(), min_length=1)
        filter_type = serializers.CharField(allow_blank=True)
        filter_content = serializers.DictField()
        remark = serializers.CharField(required=False, allow_blank=True)
        preview_directory = serializers.CharField(required=True)
        preview_ip_list = serializers.ListField(child=serializers.DictField())
        preview_time_range = serializers.CharField(required=True)
        preview_start_time = serializers.CharField(required=False, allow_blank=True)
        preview_end_time = serializers.CharField(required=False, allow_blank=True)
        preview_is_search_child = serializers.BooleanField(required=True)
        link_id = serializers.IntegerField(required=False, allow_null=True)

    def perform_request(self, validated_request_data):
        return api.log_search.create_log_extract_task(**validated_request_data)


class GetLogExtractTaskResource(Resource):
    """查询日志提取任务详情。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        task_id = serializers.IntegerField(required=True, min_value=1)

    def perform_request(self, validated_request_data):
        return api.log_search.get_log_extract_task(**validated_request_data)


class GetLogExtractDownloadUrlResource(Resource):
    """获取已完成日志提取任务的下载地址。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        task_id = serializers.IntegerField(required=True, min_value=1)

    def perform_request(self, validated_request_data):
        return api.log_search.get_log_extract_download_url(**validated_request_data, is_url="1")
