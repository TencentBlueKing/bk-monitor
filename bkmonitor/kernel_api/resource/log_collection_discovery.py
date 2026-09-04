"""日志采集 MCP 使用的发现类资源：存储集群列表、结果表/索引列表。"""

from rest_framework import serializers

from core.drf_resource import Resource, api


class ListThirdPartyESClustersResource(Resource):
    """查询当前业务可用的第三方 ES 存储集群列表。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        return api.log_search.list_log_cluster(bk_biz_id=validated_request_data["bk_biz_id"])


class ListResultTablesResource(Resource):
    """查询可接入的结果表/索引列表，用于创建 bkdata 或第三方 ES 索引集。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        scenario_id = serializers.ChoiceField(required=True, choices=["bkdata", "es"], label="接入场景")
        storage_cluster_id = serializers.IntegerField(required=False, min_value=1, label="存储集群ID")
        result_table_id = serializers.CharField(required=False, allow_blank=True, label="索引名")

        def validate(self, attrs):
            if attrs["scenario_id"] == "es" and not attrs.get("storage_cluster_id"):
                raise serializers.ValidationError({"storage_cluster_id": "第三方 ES 场景必须指定存储集群ID。"})
            return attrs

    def perform_request(self, validated_request_data):
        return api.log_search.list_result_tables(**validated_request_data)
