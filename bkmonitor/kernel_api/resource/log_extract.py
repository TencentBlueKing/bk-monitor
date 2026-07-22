"""日志提取 MCP 资源。"""

from rest_framework import serializers

from core.drf_resource import Resource, api


def build_business_scope(bk_biz_id):
    return [{"scope_type": "biz", "scope_id": str(bk_biz_id)}]


class ListLogExtractTopologyResource(Resource):
    """查询用户日志提取策略允许访问的拓扑。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        return api.log_search.list_log_extract_topology(scope_list=build_business_scope(bk_biz_id))


class SearchLogExtractHostsResource(Resource):
    """查询用户日志提取策略允许访问的主机。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        node_list = serializers.ListField(child=serializers.DictField(), required=False, min_length=1)
        search_content = serializers.CharField(required=False, allow_blank=True)
        start = serializers.IntegerField(required=False, default=0, min_value=0)
        page_size = serializers.IntegerField(required=False, default=-1, min_value=-1, max_value=500)

    def perform_request(self, validated_request_data):
        params = validated_request_data.copy()
        bk_biz_id = params.pop("bk_biz_id")
        params["scope_list"] = build_business_scope(bk_biz_id)
        params.setdefault("node_list", [{"object_id": "biz", "instance_id": bk_biz_id}])
        return api.log_search.query_log_extract_hosts(**params)


class ListLogExtractAllowedPathsResource(Resource):
    """查询所选主机或拓扑在日志提取策略下允许访问的目录。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        target_node_type = serializers.ChoiceField(
            choices=("INSTANCE", "TOPO", "SERVICE_TEMPLATE"), required=False, default="INSTANCE"
        )
        ip_list = serializers.ListField(child=serializers.DictField(), required=False, min_length=1)
        target_nodes = serializers.ListField(child=serializers.DictField(), required=False, min_length=1)

    def perform_request(self, validated_request_data):
        return api.log_search.list_log_extract_allowed_paths(**validated_request_data)


class SearchLogExtractFilesResource(Resource):
    """查询用户日志提取策略允许访问的文件。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        ip_list = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=10)
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
