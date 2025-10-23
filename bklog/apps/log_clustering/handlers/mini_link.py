import json

from apps.api import TransferApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import MINI_CLUSTERING_CONFIG
from apps.log_clustering.constants import RegexRuleTypeEnum
from apps.log_clustering.exceptions import ClusteringAccessNotSupportedException
from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs
from apps.log_clustering.handlers.regex_template import RegexTemplateHandler
from apps.log_clustering.models import ClusteringConfig
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.etl.transfer import TransferEtlHandler
from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import TimeFieldTypeEnum, TimeFieldUnitEnum
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.models import LogIndexSet, Scenario
from apps.models import model_to_dict
from bkm_space.utils import space_uid_to_bk_biz_id


class MiniLinkAccessHandler:
    def __init__(self, index_set_id: int):
        self.index_set: LogIndexSet = LogIndexSet.objects.get(pk=index_set_id)
        self.default_conf = {}
        if feature_obj := FeatureToggleObject.toggle(MINI_CLUSTERING_CONFIG):
            self.default_conf = feature_obj.feature_config

        if not self.index_set.collector_config_id:
            raise ClusteringAccessNotSupportedException()
        try:
            self.collector_config: CollectorConfig = CollectorConfig.objects.get(pk=self.index_set.collector_config_id)
        except CollectorConfig.DoesNotExist:
            raise ClusteringAccessNotSupportedException()

    def read_config(self, params: dict, key: str):
        """
        读取配置键值对
        优先级：参数传入 -> 数据库默认配置 -> 代码默认配置
        """
        if key in params:
            return params[key]
        if key in self.default_conf:
            return self.default_conf[key]
        if hasattr(OnlineTaskTrainingArgs, key.upper()):
            return getattr(OnlineTaskTrainingArgs, key.upper())
        raise AttributeError(f"clustering config key({key}) is not set")

    def access(self, params):
        """
        创建或更新配置
        """
        signature_pattern_rt = CollectorHandler.build_result_table_id(
            self.collector_config.get_bk_biz_id(),
            self.collector_config.collector_config_name_en,
            is_pattern_rt=True,
        )

        clustering_config, created = ClusteringConfig.objects.get_or_create(
            index_set_id=self.index_set.index_set_id,
            defaults=dict(
                collector_config_id=self.index_set.collector_config_id,
                min_members=self.read_config(params, "min_members"),
                max_dist_list=self.read_config(params, "max_dist_list"),
                st_list=self.read_config(params, "st_list"),
                predefined_varibles=self.read_config(params, "predefined_varibles"),
                depth=self.read_config(params, "depth"),
                delimeter=self.read_config(params, "delimeter"),
                max_log_length=self.read_config(params, "max_log_length"),
                is_case_sensitive=self.read_config(params, "is_case_sensitive"),
                clustering_fields=params["clustering_fields"],
                bk_biz_id=space_uid_to_bk_biz_id(self.index_set.space_uid),
                filter_rules=params.get("filter_rules", []),
                signature_enable=True,
                category_id=self.index_set.category_id,
                new_cls_strategy_enable=params.get("new_cls_strategy_enable", False),
                normal_strategy_enable=params.get("normal_strategy_enable", False),
                access_finished=False,
                log_bk_data_id=self.collector_config.bk_data_id,
                use_mini_link=True,
                predict_cluster=self.read_config(params, "predict_cluster"),
                signature_pattern_rt=signature_pattern_rt,
            ),
        )

        if created:
            # 创建的情况，关联一个正则模板
            regex_template = RegexTemplateHandler().list_templates(space_uid=self.index_set.space_uid)[0]
            clustering_config.regex_template_id = regex_template["id"]
            clustering_config.predefined_varibles = regex_template["predefined_varibles"]
            clustering_config.regex_rule_type = RegexRuleTypeEnum.TEMPLATE.value
            clustering_config.save()
            config_modified = True
        else:
            # 更新的情况，仅更新必要的字段
            update_fields = [
                "min_members",
                "max_dist_list",
                "st_list",
                "predefined_varibles",
                "depth",
                "delimeter",
                "max_log_length",
                "is_case_sensitive",
                "clustering_fields",
                "filter_rules",
                "predict_cluster",
                "regex_rule_type",
                "regex_template_id",
            ]
            config_modified = False
            for field in update_fields:
                if field in params and getattr(clustering_config, field) != params[field]:
                    setattr(clustering_config, field, params[field])
                    config_modified = True

        if config_modified:
            self.update_metadata()

        self.update_route(signature_pattern_rt)

        return model_to_dict(clustering_config)

    def update_metadata(self):
        """
        更新元数据
        """
        # 更新 data_id
        CollectorScenario.update_or_create_data_id(bk_data_id=self.collector_config.bk_data_id)

        # 更新结果表
        TransferEtlHandler(self.collector_config.collector_config_id).patch_update()

    def update_route(self, signature_pattern_rt):
        """
        更新路由，用于通过 UQ 查询 pattern 数据
        """
        TransferApi.create_or_update_log_router(
            {
                "cluster_id": self.index_set.storage_cluster_id,
                "index_set": signature_pattern_rt,
                "source_type": Scenario.LOG,
                "data_label": BaseIndexSetHandler.get_data_label(
                    self.index_set.index_set_id,
                    pattern_rt=True,
                ),
                "table_id": BaseIndexSetHandler.get_rt_id(
                    self.index_set.index_set_id,
                    signature_pattern_rt,
                ),
                "space_id": self.index_set.space_uid.split("__")[-1],
                "space_type": self.index_set.space_uid.split("__")[0],
                "need_create_index": False,
                "options": [
                    {
                        "name": "time_field",
                        "value_type": "dict",
                        "value": json.dumps(
                            {
                                "name": "dtEventTimeStamp",
                                "type": self.index_set.time_field_type,
                                "unit": self.index_set.time_field_unit
                                if self.index_set.time_field_type != TimeFieldTypeEnum.DATE.value
                                else TimeFieldUnitEnum.MILLISECOND.value,
                            }
                        ),
                    },
                    {
                        "name": "need_add_time",
                        "value_type": "bool",
                        "value": "true",
                    },
                ],
            }
        )
