"""API Gateway resources exposed by BlueKing Log for log extraction."""

from rest_framework import serializers

from api.log_search.default import LogSearchAPIGWResource


class QueryLogExtractHostsResource(LogSearchAPIGWResource):
    action = "/log_extract/explorer/query_hosts/"
    method = "POST"


class ListLogExtractFilesResource(LogSearchAPIGWResource):
    action = "/log_extract/explorer/list_file/"
    method = "POST"


class CreateLogExtractTaskResource(LogSearchAPIGWResource):
    action = "/log_extract/tasks/"
    method = "POST"


class GetLogExtractTaskResource(LogSearchAPIGWResource):
    action = "/log_extract/tasks/{task_id}/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.IntegerField(required=True, min_value=1)
        bk_biz_id = serializers.IntegerField(required=True)

    def get_request_url(self, validated_request_data):
        url = self.base_url.rstrip("/") + "/" + self.action.lstrip("/")
        return url.format(task_id=validated_request_data.pop("task_id"))


class GetLogExtractDownloadUrlResource(LogSearchAPIGWResource):
    action = "/log_extract/tasks/download/"
    method = "GET"
