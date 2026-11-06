"""业务场景存储查询的 HTTP 入参；SaaS 与内部 Metadata 接口共用。"""

from rest_framework import serializers


SCENE_DATA_TYPES = {
    "bcs": ("k8s_metric", "custom_metric", "k8s_event", "custom_event", "system_log", "custom_log"),
    "plugin": ("metric", "event", "process_perf", "process_port"),
    "collect_config": ("metric", "event", "process_perf", "process_port"),
    "custom_metric": ("metric",),
    "custom_event": ("event",),
    "uptime_check": ("http", "tcp", "udp", "icmp"),
    "apm": ("metric", "trace", "log", "profile"),
    "host": ("base", "process_perf", "process_port", "event"),
    "recording_rule": ("metric",),
}


class ResourceStorageSelectorSerializer(serializers.Serializer):
    scene = serializers.ChoiceField(choices=tuple(SCENE_DATA_TYPES))
    resource_ids = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    data_types = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate(self, attrs):
        if set(attrs["data_types"]) - set(SCENE_DATA_TYPES[attrs["scene"]]):
            raise serializers.ValidationError({"data_types": "数据类别不属于指定场景"})
        return attrs


class QueryResourceStorageSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField()
    selectors = ResourceStorageSelectorSerializer(many=True, required=False, default=list)
    include_runtime = serializers.BooleanField(default=False)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=1000, default=100)


def matches_selector(reference: dict, selectors: list[dict]) -> bool:
    """同一场景的多个 selector 取并集，空列表表示全部。"""
    return not selectors or any(
        reference["scene"] == selector["scene"]
        and (not selector.get("resource_ids") or reference["resource_id"] in selector["resource_ids"])
        and (not selector.get("data_types") or reference["data_type"] in selector["data_types"])
        for selector in selectors
    )
