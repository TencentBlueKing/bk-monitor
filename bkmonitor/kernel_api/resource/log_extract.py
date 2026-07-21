"""MCP-facing resources for extracting files from BlueKing Log managed hosts."""

import posixpath

from rest_framework import serializers

from core.drf_resource import Resource, api


class HostReferenceSerializer(serializers.Serializer):
    bk_host_id = serializers.IntegerField(required=True, min_value=1)
    ip = serializers.IPAddressField(required=True)
    bk_cloud_id = serializers.IntegerField(required=True)


class SearchLogExtractHostsResource(Resource):
    """Resolve an exact IP to hosts accessible under the user's log-extraction strategies."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        ip = serializers.IPAddressField(required=True, protocol="IPv4")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        result = api.log_search.query_log_extract_hosts(
            scope_list=[{"scope_type": "biz", "scope_id": str(bk_biz_id)}],
            node_list=[{"object_id": "biz", "instance_id": bk_biz_id}],
            search_condition={"ip": validated_request_data["ip"]},
            start=0,
            page_size=20,
        )

        hosts = []
        for host in result.get("data", []):
            cloud_area = host.get("cloud_area") or {}
            hosts.append(
                {
                    "bk_host_id": host.get("host_id"),
                    "ip": host.get("ip"),
                    "bk_cloud_id": cloud_area.get("id"),
                    "bk_cloud_name": cloud_area.get("name", ""),
                    "host_name": host.get("host_name", ""),
                    "alive": host.get("alive"),
                }
            )

        if not hosts:
            resolution = "NOT_FOUND"
        elif len(hosts) == 1:
            resolution = "RESOLVED"
        else:
            resolution = "AMBIGUOUS"
        return {"resolution": resolution, "total": len(hosts), "hosts": hosts}


class SearchLogExtractFilesResource(Resource):
    """Search files after resolving the target hosts."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        ip_list = serializers.ListField(child=HostReferenceSerializer(), min_length=1, max_length=20)
        path = serializers.CharField(required=True, max_length=255)
        is_search_child = serializers.BooleanField(required=False, default=False)
        time_range = serializers.ChoiceField(required=False, default="1d", choices=["1d", "1w", "1m", "all", "custom"])
        start_time = serializers.CharField(required=False, allow_blank=True, default="")
        end_time = serializers.CharField(required=False, allow_blank=True, default="")
        limit = serializers.IntegerField(required=False, default=100, min_value=1, max_value=100)

        def validate(self, attrs):
            if attrs["time_range"] == "custom" and not (attrs["start_time"] and attrs["end_time"]):
                raise serializers.ValidationError("start_time and end_time are required for a custom time range")
            return attrs

    def perform_request(self, validated_request_data):
        limit = validated_request_data.pop("limit")
        files = api.log_search.list_log_extract_files(**validated_request_data) or []
        return {
            "total": len(files),
            "files": files[:limit],
            "truncated": len(files) > limit,
        }


class CreateLogExtractTaskMCPResource(Resource):
    """Create an asynchronous log-extraction task using the server-side default link."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        ip_list = serializers.ListField(child=HostReferenceSerializer(), min_length=1, max_length=20)
        file_path = serializers.ListField(child=serializers.CharField(max_length=255), min_length=1, max_length=10)
        filter_type = serializers.ChoiceField(
            required=False,
            default="",
            allow_blank=True,
            choices=["", "line_range", "match_word", "tail_line", "match_range"],
        )
        filter_content = serializers.DictField(required=False, default=dict)
        remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def perform_request(self, validated_request_data):
        file_paths = validated_request_data["file_path"]
        parent_dirs = [posixpath.dirname(path.rstrip("/")) or "/" for path in file_paths]
        try:
            preview_directory = posixpath.commonpath(parent_dirs)
        except ValueError:
            preview_directory = "/"

        request_data = {
            **validated_request_data,
            "target_node_type": "INSTANCE",
            "preview_directory": preview_directory,
            "preview_ip_list": validated_request_data["ip_list"],
            "preview_time_range": "all",
            "preview_start_time": "",
            "preview_end_time": "",
            "preview_is_search_child": False,
        }
        result = api.log_search.create_log_extract_task(**request_data)
        return {"task_id": result["task_id"], "status": "QUEUED", "poll_after_seconds": 5}


class GetLogExtractTaskMCPResource(Resource):
    """Get a normalized log-extraction task status."""

    STATUS_MAPPING = {
        "init": "QUEUED",
        "pipeline": "RUNNING",
        "packing": "RUNNING",
        "distributing": "RUNNING",
        "distributing_packing": "RUNNING",
        "uploading": "RUNNING",
        "cstone_uploading": "RUNNING",
        "cos_upload": "RUNNING",
        "downloadable": "SUCCEEDED",
        "failed": "FAILED",
        "expired": "EXPIRED",
    }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        task_id = serializers.IntegerField(required=True, min_value=1)

    def perform_request(self, validated_request_data):
        result = api.log_search.get_log_extract_task(**validated_request_data)
        if int(result.get("bk_biz_id", 0)) != validated_request_data["bk_biz_id"]:
            raise serializers.ValidationError("task does not belong to the requested business")

        raw_status = result.get("download_status", "")
        return {
            "task_id": result.get("task_id"),
            "status": self.STATUS_MAPPING.get(raw_status, "RUNNING"),
            "stage": raw_status.upper(),
            "message": result.get("download_status_display") or result.get("task_process_info") or "",
            "download_ready": raw_status == "downloadable",
            "created_at": result.get("created_at"),
            "expires_at": result.get("expiration_date"),
            "failure": result.get("task_process_info") if raw_status == "failed" else None,
        }


class GetLogExtractDownloadUrlMCPResource(Resource):
    """Get a short-lived download URL for a completed extraction task."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        task_id = serializers.IntegerField(required=True, min_value=1)

    def perform_request(self, validated_request_data):
        download_url = api.log_search.get_log_extract_download_url(**validated_request_data, is_url="1")
        return {"task_id": validated_request_data["task_id"], "download_url": download_url}
