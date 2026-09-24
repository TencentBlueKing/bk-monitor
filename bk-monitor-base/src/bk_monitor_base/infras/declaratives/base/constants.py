import copy
from enum import Enum

ES_MAX_MAPPING_FIELDS = 5000
ES_MAX_OFFSET = 50000
ES_NUMBER_OF_SHARDS = 3
ES_NUMBER_OF_REPLICAS = 2


class ModelFieldDefinition(str, Enum):
    CHAR_FIELD = "models.CharField(max_length=255, null=True)"
    INT_FIELD = "models.IntegerField(null=True)"
    FLOAT_FIELD = "models.FloatField(null=True)"
    BOOLEAN_FIELD = "models.BooleanField(null=True)"
    UUID_FIELD = "models.UUIDField(null=True)"
    JSON_FIELD = "models.JSONField(null=True)"


class ModelFieldDefinitionWithDefault(str, Enum):
    CHAR_FIELD = "models.CharField(max_length=255, null=True, default='')"
    INT_FIELD = "models.IntegerField(null=True, default=0)"
    FLOAT_FIELD = "models.FloatField(null=True, default=0.0)"
    BOOLEAN_FIELD = "models.BooleanField(null=True, default=False)"
    UUID_FIELD = "models.UUIDField(null=True, default=uuid.uuid4)"
    JSON_FIELD = "models.JSONField(null=True, default=dict)"


default_es_model_settings = {
    "refresh_interval": "1s",
    "max_result_window": ES_MAX_OFFSET,  # from/size分页最大offset
    "max_terms_count": 65535 * 3,  # terms匹配最大条件数
    "number_of_shards": ES_NUMBER_OF_SHARDS,
    "number_of_replicas": ES_NUMBER_OF_REPLICAS,
    "mapping.total_fields.limit": ES_MAX_MAPPING_FIELDS,
}

# TODO ILM策略(待确定)
DEFAULT_ES_ILM_POLICY_SETTINGS = {
    "policy": {
        "phases": {
            "hot": {
                "actions": {
                    "rollover": {
                        "max_age": "7d",
                        "max_size": "20gb",
                    },
                    "set_priority": {"priority": 100},
                }
            },
            "delete": {"min_age": "90d", "actions": {"delete": {}}},
        }
    }
}

DEFAULT_USE_ES_STORE_RESOURCE = ["CMDBEvent", "ResourceEvent"]


def es_model_conf_merge(param: dict):
    conf = copy.deepcopy(default_es_model_settings)
    conf.update(param)
    return conf
