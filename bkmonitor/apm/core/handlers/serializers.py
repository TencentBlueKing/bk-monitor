from django.utils.translation import gettext_lazy as _

from rest_framework import serializers


class ApplicationStorageRouteSerializer(serializers.Serializer):
    class RuleSerializer(serializers.Serializer):
        space_type = serializers.CharField(label=_("空间类型"), max_length=255, allow_blank=True)
        name__reg = serializers.CharField(label=_("应用名称正则"), max_length=255, allow_blank=True)

    class StorageSerializer(serializers.Serializer):
        es_storage_cluster_id = serializers.IntegerField(label=_("es存储集群"))

    rule = RuleSerializer(label=_("规则"))
    storage = StorageSerializer(label=_("存储配置"))
