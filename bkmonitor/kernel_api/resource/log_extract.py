"""日志提取 MCP 资源。"""

import ntpath
import posixpath

from rest_framework import serializers

from core.drf_resource import Resource, api


FILE_SEARCH_RESULT_LIMIT = 100
TASK_STATE_BY_DOWNLOAD_STATUS = {
    "init": "pending",
    "pipeline": "running",
    "packing": "running",
    "distributing": "running",
    "distributing_packing": "running",
    "uploading": "running",
    "cstone_uploading": "running",
    "cos_upload": "running",
    "downloadable": "downloadable",
    "failed": "failed",
    "expired": "expired",
}
TERMINAL_TASK_STATES = {"downloadable", "failed", "expired", "unknown"}


def build_business_scope(bk_biz_id):
    return [{"scope_type": "biz", "scope_id": str(bk_biz_id)}]


def build_bklog_target_nodes(target_nodes):
    return [
        {
            "bk_obj_id": node.get("object_id", node.get("bk_obj_id")),
            "bk_inst_id": node.get("instance_id", node.get("bk_inst_id")),
        }
        for node in target_nodes
    ]


def get_preview_directory(file_path):
    path_module = ntpath if "\\" in file_path else posixpath
    return path_module.dirname(file_path) or file_path


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
        page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=500)

    def perform_request(self, validated_request_data):
        params = validated_request_data.copy()
        bk_biz_id = params.pop("bk_biz_id")
        params["scope_list"] = build_business_scope(bk_biz_id)
        params.setdefault("node_list", [{"object_id": "biz", "instance_id": bk_biz_id}])
        result = api.log_search.query_log_extract_hosts(**params)
        for host in result.get("data", []):
            if "host_id" in host:
                host.setdefault("bk_host_id", host["host_id"])
            if "cloud_id" in host:
                host.setdefault("bk_cloud_id", host["cloud_id"])
        return result


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
        params = validated_request_data.copy()
        if "target_nodes" in params:
            params["target_nodes"] = build_bklog_target_nodes(params["target_nodes"])
        return api.log_search.list_log_extract_allowed_paths(**params)


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
        files = api.log_search.list_log_extract_files(**validated_request_data)
        return {
            "total": len(files),
            "data": files[:FILE_SEARCH_RESULT_LIMIT],
            "truncated": len(files) > FILE_SEARCH_RESULT_LIMIT,
        }


class CreateLogExtractTaskResource(Resource):
    """创建异步日志提取任务。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        target_node_type = serializers.ChoiceField(
            choices=("INSTANCE", "TOPO", "SERVICE_TEMPLATE"), required=False, default="INSTANCE"
        )
        ip_list = serializers.ListField(child=serializers.DictField(), required=False)
        target_nodes = serializers.ListField(child=serializers.DictField(), required=False)
        file_path = serializers.ListField(child=serializers.CharField(), min_length=1)
        filter_type = serializers.CharField(allow_blank=True)
        filter_content = serializers.DictField()
        remark = serializers.CharField(required=False, allow_blank=True)
        preview_directory = serializers.CharField(required=False)
        preview_ip_list = serializers.ListField(child=serializers.DictField(), required=False)
        preview_time_range = serializers.ChoiceField(choices=("1d", "1w", "1m", "all", "custom"), required=False)
        preview_start_time = serializers.CharField(required=False, allow_blank=True)
        preview_end_time = serializers.CharField(required=False, allow_blank=True)
        preview_is_search_child = serializers.BooleanField(required=False)
        link_id = serializers.IntegerField(required=False, allow_null=True)

    def perform_request(self, validated_request_data):
        params = validated_request_data.copy()
        if "target_nodes" in params:
            params["target_nodes"] = build_bklog_target_nodes(params["target_nodes"])
        params.setdefault("preview_directory", get_preview_directory(params["file_path"][0]))
        params.setdefault("preview_ip_list", [])
        params.setdefault("preview_time_range", "all")
        params.setdefault("preview_is_search_child", False)
        return api.log_search.create_log_extract_task(**params)


class GetLogExtractTaskResource(Resource):
    """查询日志提取任务详情。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        task_id = serializers.IntegerField(required=True, min_value=1)

    def perform_request(self, validated_request_data):
        task = api.log_search.get_log_extract_task(**validated_request_data)
        raw_state = task.get("download_status")
        state = TASK_STATE_BY_DOWNLOAD_STATUS.get(raw_state, "unknown")
        error = None
        if state == "failed":
            error = task.get("task_process_info") or "Log extraction task failed."
        elif state == "unknown":
            error = f"Unsupported BK Log task status: {raw_state}"

        return {
            "task_id": task.get("task_id", validated_request_data["task_id"]),
            "bk_biz_id": task.get("bk_biz_id", validated_request_data["bk_biz_id"]),
            "state": state,
            "raw_state": raw_state,
            "terminal": state in TERMINAL_TASK_STATES,
            "downloadable": state == "downloadable",
            "error": error,
        }


class GetLogExtractDownloadUrlResource(Resource):
    """获取已完成日志提取任务的下载地址。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        task_id = serializers.IntegerField(required=True, min_value=1)

    def perform_request(self, validated_request_data):
        return api.log_search.get_log_extract_download_url(**validated_request_data, is_url="1")
