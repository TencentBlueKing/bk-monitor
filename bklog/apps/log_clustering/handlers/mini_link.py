from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import MINI_CLUSTERING_CONFIG
from apps.log_clustering.constants import RegexRuleTypeEnum
from apps.log_clustering.exceptions import ClusteringAccessNotSupportedException
from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs
from apps.log_clustering.handlers.regex_template import RegexTemplateHandler
from apps.log_clustering.models import ClusteringConfig
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet
from apps.models import model_to_dict
from bkm_space.utils import space_uid_to_bk_biz_id


class MiniLinkAccessHandler:
    def __init__(self, index_set_id: int):
        self.index_set: LogIndexSet = LogIndexSet.objects.get(pk=index_set_id)
        self.default_conf: dict = FeatureToggleObject.toggle(MINI_CLUSTERING_CONFIG).feature_config or {}

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
                signature_pattern_rt=CollectorHandler.build_result_table_id(
                    self.collector_config.get_bk_biz_id(),
                    self.collector_config.collector_config_name_en,
                    is_pattern_rt=True,
                ),
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
        return model_to_dict(clustering_config)

    def update_metadata(self):
        """
        更新元数据
        """
        # 更新 data_id
        CollectorScenario.update_or_create_data_id(bk_data_id=self.collector_config.bk_data_id)

        # 更新结果表
