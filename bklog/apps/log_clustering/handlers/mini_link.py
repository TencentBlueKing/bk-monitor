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
from apps.utils.log import logger
from bkm_space.utils import space_uid_to_bk_biz_id, parse_space_uid


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
        logger.info(
            "[mini_link] Start MiniLink access process: index_set_id=%s, space_uid=%s, params_keys=%s",
            self.index_set.index_set_id,
            self.index_set.space_uid,
            list(params.keys()),
        )
        signature_pattern_rt = CollectorHandler.build_result_table_id(
            self.collector_config.get_bk_biz_id(),
            self.collector_config.collector_config_name_en,
            is_pattern_rt=True,
        )
        logger.info(
            "[mini_link] Generated signature pattern result table ID: index_set_id=%s, signature_pattern_rt=%s",
            self.index_set.index_set_id,
            signature_pattern_rt,
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
                access_finished=True,
                log_bk_data_id=self.collector_config.bk_data_id,
                use_mini_link=True,
                predict_cluster=self.read_config(params, "predict_cluster"),
                signature_pattern_rt=signature_pattern_rt,
            ),
        )

        if created:
            # 创建的情况，关联一个正则模板
            logger.info("[mini_link] Create new clustering config: index_set_id=%s", self.index_set.index_set_id)
            regex_template = RegexTemplateHandler().list_templates(space_uid=self.index_set.space_uid)[0]
            clustering_config.regex_template_id = regex_template["id"]
            clustering_config.predefined_varibles = regex_template["predefined_varibles"]
            clustering_config.regex_rule_type = RegexRuleTypeEnum.TEMPLATE.value
            clustering_config.save()
            logger.info(
                "[mini_link] Successfully created clustering config and linked regex template: index_set_id=%s, regex_template_id=%s",
                self.index_set.index_set_id,
                regex_template["id"],
            )
            config_modified = True
        else:
            # 更新的情况，仅更新必要的字段
            logger.info("[mini_link] Update existing clustering config: index_set_id=%s", self.index_set.index_set_id)
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
            updated_field_list = []
            for field in update_fields:
                if field in params and getattr(clustering_config, field) != params[field]:
                    setattr(clustering_config, field, params[field])
                    updated_field_list.append(field)
                    config_modified = True
            if updated_field_list:
                clustering_config.save(update_fields=updated_field_list)
                logger.info(
                    "[mini_link] Successfully updated clustering config fields: index_set_id=%s, updated_fields=%s",
                    self.index_set.index_set_id,
                    updated_field_list,
                )
            else:
                logger.info(
                    "[mini_link] Clustering config needs no update: index_set_id=%s", self.index_set.index_set_id
                )

        if config_modified:
            logger.info(
                "[mini_link] Config modified, start updating metadata: index_set_id=%s", self.index_set.index_set_id
            )
            self.update_metadata()
        else:
            logger.info(
                "[mini_link] Config not modified, skip metadata update: index_set_id=%s", self.index_set.index_set_id
            )

        logger.info(
            "[mini_link] Start updating route config: index_set_id=%s, signature_pattern_rt=%s",
            self.index_set.index_set_id,
            signature_pattern_rt,
        )
        self.update_route(signature_pattern_rt)

        logger.info(
            "[mini_link] MiniLink access process completed: index_set_id=%s, created=%s",
            self.index_set.index_set_id,
            created,
        )
        return model_to_dict(clustering_config)

    def update_metadata(self):
        """
        更新元数据
        """
        logger.info(
            "[mini_link] Start updating metadata: index_set_id=%s, bk_data_id=%s, collector_config_id=%s",
            self.index_set.index_set_id,
            self.collector_config.bk_data_id,
            self.collector_config.collector_config_id,
        )
        # 更新 data_id
        try:
            CollectorScenario.update_or_create_data_id(bk_data_id=self.collector_config.bk_data_id)
            logger.info(
                "[mini_link] Successfully updated/created data_id: index_set_id=%s, bk_data_id=%s",
                self.index_set.index_set_id,
                self.collector_config.bk_data_id,
            )
        except Exception as e:
            logger.exception(
                "[mini_link] Failed to update data_id: index_set_id=%s, bk_data_id=%s, error=%s",
                self.index_set.index_set_id,
                self.collector_config.bk_data_id,
                e,
            )
            raise

        # 更新结果表
        try:
            TransferEtlHandler(self.collector_config.collector_config_id).patch_update()
            logger.info(
                "[mini_link] Successfully updated ETL result table: index_set_id=%s, collector_config_id=%s",
                self.index_set.index_set_id,
                self.collector_config.collector_config_id,
            )
        except Exception as e:
            logger.exception(
                "[mini_link] Failed to update ETL result table: index_set_id=%s, collector_config_id=%s, error=%s",
                self.index_set.index_set_id,
                self.collector_config.collector_config_id,
                e,
            )
            raise

    def update_route(self, signature_pattern_rt):
        """
        更新路由，用于通过 UQ 查询 pattern 数据
        """
        space_type, space_id = parse_space_uid(self.index_set.space_uid)
        logger.info(
            "[mini_link] Start updating route: index_set_id=%s, signature_pattern_rt=%s, space_type=%s, space_id=%s",
            self.index_set.index_set_id,
            signature_pattern_rt,
            space_type,
            space_id,
        )

        try:
            TransferApi.bulk_create_or_update_log_router(
                {
                    "data_label": BaseIndexSetHandler.get_data_label(
                        self.index_set.index_set_id,
                        pattern_rt=True,
                    ),
                    "space_id": space_id,
                    "space_type": space_type,
                    "table_info": [
                        {
                            "table_id": BaseIndexSetHandler.get_rt_id(
                                self.index_set.index_set_id,
                                signature_pattern_rt,
                            ),
                            "index_set": signature_pattern_rt.replace(".", "_"),
                            "source_type": Scenario.LOG,
                            "cluster_id": self.index_set.storage_cluster_id,
                            "options": [
                                {
                                    "name": "time_field",
                                    "value_type": "dict",
                                    "value": json.dumps(
                                        {
                                            "name": self.index_set.time_field,
                                            "type": self.index_set.time_field_type,
                                            "unit": self.index_set.time_field_unit
                                            if self.index_set.time_field_type != TimeFieldTypeEnum.DATE.value
                                            else TimeFieldUnitEnum.MILLISECOND.value,
                                        }
                                    ),
                                },
                                {"name": "need_add_time", "value_type": "bool", "value": "true"},
                            ],
                        }
                    ],
                }
            )
            logger.info(
                "[mini_link] Successfully updated route config: index_set_id=%s, signature_pattern_rt=%s",
                self.index_set.index_set_id,
                signature_pattern_rt,
            )
        except Exception as e:
            logger.exception(
                "[mini_link] Failed to update route config: index_set_id=%s, signature_pattern_rt=%s, error=%s",
                self.index_set.index_set_id,
                signature_pattern_rt,
                e,
            )
            raise
