import os
from collections import defaultdict

from django.core.management import BaseCommand, CommandError
from django.db import transaction

from apps.log_clustering.models import (
    AiopsModel,
    AiopsModelExperiment,
    AiopsSignatureAndPattern,
    SampleSet,
    RegexTemplate,
    ClusteringRemark,
    ClusteringConfig,
    ClusteringSubscription,
    NoticeGroup,
    SignatureStrategySettings,
)
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.utils.local import activate_request
from apps.utils.thread import generate_request
from bkm_space.utils import bk_biz_id_to_space_uid
from home_application.management.commands.migrate_tool import (
    parse_str_int_list,
    JsonFile,
    Prompt,
)

PROJECT_PATH = os.getcwd()


class Command(BaseCommand):
    """海外迁移指令类"""

    def add_arguments(self, parser):
        parser.add_argument("-b", "--bk_biz_id", help="需要导入的业务, 不传时导入所有的业务", type=int, default=0)
        parser.add_argument(
            "--index_set_ids", help="需要导入的索引集 ID, 不传时导入所有的索引集, 例如: 1,2,3", type=str, default=""
        )
        parser.add_argument(
            "-dp",
            "--dir_path",
            type=str,
            help="存放 json 文件的文件夹路径",
            default=PROJECT_PATH,
        )
        parser.add_argument(
            "--is_first_execute", type=bool, help="该环境下是否第一次执行此迁移指令, 例如: True", required=True
        )

    def handle(self, *args, **options):
        dir_path = options["dir_path"]

        json_filepath_dict = {
            "index_set": os.path.join(dir_path, "log_search_logindexset.json"),
            "index_set_data": os.path.join(dir_path, "log_search_logindexsetdata.json"),
            "collector_config": os.path.join(dir_path, "log_databus_collectorconfig.json"),
            "container_collector_config": os.path.join(dir_path, "log_databus_containercollectorconfig.json"),
            "aiops_model": os.path.join(dir_path, "log_clustering_aiopsmodel.json"),
            "aiops_model_experiment": os.path.join(dir_path, "log_clustering_aiopsmodelexperiment.json"),
            "aiops_signature_and_pattern": os.path.join(dir_path, "log_clustering_aiopssignatureandpattern.json"),
            "clustering_config": os.path.join(dir_path, "log_clustering_clusteringconfig.json"),
            "clustering_remark": os.path.join(dir_path, "log_clustering_clusteringremark.json"),
            "clustering_subscription": os.path.join(dir_path, "log_clustering_clusteringsubscription.json"),
            "notice_group": os.path.join(dir_path, "log_clustering_noticegroup.json"),
            "regex_template": os.path.join(dir_path, "log_clustering_regextemplate.json"),
            "sample_set": os.path.join(dir_path, "log_clustering_sampleset.json"),
            "signature_strategy_settings": os.path.join(dir_path, "log_clustering_signaturestrategysettings.json"),
        }

        json_content_dict = {}

        for key, json_filepath in json_filepath_dict.items():
            if not os.path.exists(json_filepath):
                raise CommandError(f"json 文件不存在: {json_filepath}")

            if not json_filepath.endswith(".json"):
                raise CommandError(f"json 文件格式错误(.json): {json_filepath}")

            try:
                json_content = JsonFile.read(json_filepath)
            except Exception as e:
                error_msg = f"json 文件读取失败: {json_filepath}, 错误原因：{str(e)}"
                raise CommandError(error_msg) from e

            json_content_dict[key] = json_content

        OverseasMigrateTool(
            json_content_dict=json_content_dict,
            is_first_execute=options["is_first_execute"],
            bk_biz_id=options["bk_biz_id"],
            index_set_ids_str=options["index_set_ids"],
        ).migrate()


class OverseasMigrateTool:
    """海外迁移工具类"""

    def __init__(self, json_content_dict: dict, is_first_execute, bk_biz_id: int = 0, index_set_ids_str: str = ""):
        self.is_first_execute = is_first_execute
        self.json_content_dict = json_content_dict
        self.bk_biz_id = bk_biz_id
        self.space_uid = ""
        if self.bk_biz_id:
            self.space_uid = bk_biz_id_to_space_uid(self.bk_biz_id)
        self.index_set_id_set = set(parse_str_int_list(index_set_ids_str))

    @transaction.atomic
    def migrate(self):
        """
        原数据迁移
        """
        index_set_id_set = set()
        if self.bk_biz_id and self.space_uid:
            index_set_file_datas = [
                data
                for data in self.json_content_dict.get("index_set", [])
                if data.get("space_uid", "") == self.space_uid
            ]
            index_set_id_set = set(
                [data.get("index_set_id") for data in index_set_file_datas if data.get("index_set_id")]
            )
        else:
            index_set_file_datas = self.json_content_dict.get("index_set", [])

        if not self.index_set_id_set and index_set_id_set:
            self.index_set_id_set = index_set_id_set

        aiops_model_success_migrate_ids = []
        aiops_model_experiment_success_migrate_ids = []
        aiops_signature_and_pattern_success_migrate_ids = []
        sample_set_success_migrate_ids = []
        index_set_success_migrate_index_set_ids = []
        index_set_data_success_migrate_index_ids = []
        collector_config_success_migrate_collector_config_ids = []
        container_collector_config_success_migrate_ids = []
        clustering_config_success_migrate_ids = []
        clustering_subscription_success_migrate_ids = []
        notice_group_success_migrate_ids = []
        signature_strategy_settings_success_migrate_ids = []

        if self.is_first_execute:
            # 无外键关联, 直接迁移
            try:
                aiops_model_objs = self.file_datas_save_db(AiopsModel, self.json_content_dict.get("aiops_model", []))
                aiops_model_experiment_objs = self.file_datas_save_db(
                    AiopsModelExperiment, self.json_content_dict.get("aiops_model_experiment", [])
                )
                aiops_signature_and_pattern_objs = self.file_datas_save_db(
                    AiopsSignatureAndPattern, self.json_content_dict.get("aiops_signature_and_pattern", [])
                )
                sample_set_objs = self.file_datas_save_db(SampleSet, self.json_content_dict.get("sample_set", []))
            except Exception as e:
                raise CommandError(
                    "请检查是否为该环境下第一次执行此迁移指令, 正确填充参数 is_first_execute, 例如: True"
                ) from e
            aiops_model_success_migrate_ids = [obj.id for obj in aiops_model_objs]
            aiops_model_experiment_success_migrate_ids = [obj.id for obj in aiops_model_experiment_objs]
            aiops_signature_and_pattern_success_migrate_ids = [obj.id for obj in aiops_signature_and_pattern_objs]
            sample_set_success_migrate_ids = [obj.id for obj in sample_set_objs]

        # 有外键关联, 需关联迁移
        # 创建数据字典，方便后续取值
        clustering_remark_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "bk_biz_id", self.json_content_dict.get("clustering_remark", []), bk_biz_id_set={self.bk_biz_id}
        )
        regex_template_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "space_uid", self.json_content_dict.get("regex_template", []), space_uid_set={self.space_uid}
        )
        index_set_data_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id", self.json_content_dict.get("index_set_data", []), index_set_id_set=self.index_set_id_set
        )
        collector_config_file_data_dict = self.transform_dict_list_to_customization_key_dict(
            "index_set_id", self.json_content_dict.get("collector_config", []), index_set_id_set=self.index_set_id_set
        )
        clustering_config_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id", self.json_content_dict.get("clustering_config", []), index_set_id_set=self.index_set_id_set
        )
        clustering_subscription_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id",
            self.json_content_dict.get("clustering_subscription", []),
            index_set_id_set=self.index_set_id_set,
        )
        notice_group_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id", self.json_content_dict.get("notice_group", []), index_set_id_set=self.index_set_id_set
        )
        signature_strategy_settings_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id",
            self.json_content_dict.get("signature_strategy_settings", []),
            index_set_id_set=self.index_set_id_set,
        )

        clustering_remark_file_datas = []
        regex_template_file_datas = []
        if self.bk_biz_id and self.space_uid:
            clustering_remark_file_datas = clustering_remark_file_datas_dict.get(self.bk_biz_id, [])
            regex_template_file_datas = regex_template_file_datas_dict.get(self.space_uid, [])
        else:
            for value in clustering_remark_file_datas_dict.values():
                clustering_remark_file_datas.extend(value)
            for value in regex_template_file_datas_dict.values():
                regex_template_file_datas.extend(value)

        clustering_remark_objs = self.file_datas_save_db(ClusteringRemark, clustering_remark_file_datas)
        regex_template_objs = self.file_datas_save_db(RegexTemplate, regex_template_file_datas)
        clustering_remark_success_migrate_ids = [obj.id for obj in clustering_remark_objs]
        regex_template_success_migrate_ids = [obj.id for obj in regex_template_objs]

        collector_config_id_name_dict = {}

        # 遍历索引集数据，进行迁移操作
        for data in index_set_file_datas:
            if (self.bk_biz_id and data.get("space_uid") != self.space_uid) or (
                self.index_set_id_set and data.get("index_set_id") not in self.index_set_id_set
            ):
                continue

            index_set_id = data.get("index_set_id")

            # 格式化数据为原格式
            data["tag_ids"] = self.format_multi_str_split_by_comma_field_back(data.get("tag_ids", ""))
            data["view_roles"] = self.format_multi_str_split_by_comma_field_back(data.get("view_roles", ""))

            # 通过字典取出与 index_set_id 关联的其他表数据
            index_set_data_datas = index_set_data_file_datas_dict.get(index_set_id, [])
            collector_config_data = collector_config_file_data_dict.get(index_set_id, {})
            clustering_config_datas = clustering_config_file_datas_dict.get(index_set_id, [])
            clustering_subscription_datas = clustering_subscription_file_datas_dict.get(index_set_id, [])
            notice_group_datas = notice_group_file_datas_dict.get(index_set_id, [])
            signature_strategy_settings_datas = signature_strategy_settings_file_datas_dict.get(index_set_id, [])

            if collector_config_data:
                collector_config_id = collector_config_data.get("collector_config_id")

                collector_config_id_name_dict[collector_config_id] = collector_config_data.get("collector_config_name")

                container_collector_config_file_datas_dict = (
                    self.transform_dict_list_to_customization_key_dict_list_dict(
                        "collector_config_id",
                        self.json_content_dict.get("container_collector_config", []),
                        collector_config_id_set={collector_config_id},
                    )
                )
                # 格式化为 task_id_list 原格式
                collector_config_data["task_id_list"] = self.format_multi_str_split_by_comma_field_back(
                    collector_config_data.get("task_id_list", "")
                )

                collector_config_obj = self.data_save_db(CollectorConfig, collector_config_data)
                collector_config_success_migrate_collector_config_ids.append(collector_config_obj.collector_config_id)

                container_collector_config_datas = container_collector_config_file_datas_dict.get(
                    collector_config_id, []
                )

                container_collector_config_objs = self.file_datas_save_db(
                    ContainerCollectorConfig, container_collector_config_datas
                )
                container_collector_config_success_migrate_ids.extend(
                    [obj.id for obj in container_collector_config_objs]
                )

            index_set_obj = self.data_save_db(LogIndexSet, data)
            index_set_success_migrate_index_set_ids.append(index_set_obj.index_set_id)

            index_set_data_objs = self.file_datas_save_db(LogIndexSetData, index_set_data_datas)
            index_set_data_success_migrate_index_ids.extend([obj.index_id for obj in index_set_data_objs])
            clustering_config_objs = self.file_datas_save_db(ClusteringConfig, clustering_config_datas)
            clustering_config_success_migrate_ids.extend([obj.id for obj in clustering_config_objs])
            clustering_subscription_objs = self.file_datas_save_db(
                ClusteringSubscription, clustering_subscription_datas
            )
            clustering_subscription_success_migrate_ids.extend([obj.id for obj in clustering_subscription_objs])
            notice_group_objs = self.file_datas_save_db(NoticeGroup, notice_group_datas)
            notice_group_success_migrate_ids.extend([obj.id for obj in notice_group_objs])
            signature_strategy_settings_objs = self.file_datas_save_db(
                SignatureStrategySettings, signature_strategy_settings_datas
            )
            signature_strategy_settings_success_migrate_ids.extend([obj.id for obj in signature_strategy_settings_objs])

        activate_request(generate_request("admin"))

        Prompt.info(
            msg="迁移成功 -> \n"
            "表名: 迁移成功主键列表\n"
            "log_clustering_aiopsmodel: {aiops_model_success_migrate_ids}\n"
            "log_clustering_aiopsmodelexperiment: {aiops_model_experiment_success_migrate_ids}\n"
            "log_clustering_aiopssignatureandpattern: {aiops_signature_and_pattern_success_migrate_ids}\n"
            "log_clustering_sampleset: {sample_set_success_migrate_ids}\n"
            "log_clustering_clusteringremark: {clustering_remark_success_migrate_ids}\n"
            "log_clustering_regextemplate: {regex_template_success_migrate_ids}\n"
            "log_search_logindexset: {index_set_success_migrate_index_set_ids}\n"
            "log_search_logindexsetdata: {index_set_data_success_migrate_index_ids}\n"
            "log_databus_collectorconfig: {collector_config_success_migrate_collector_config_ids}\n"
            "log_databus_containercollectorconfig: {container_collector_config_success_migrate_ids}\n"
            "log_clustering_clusteringconfig: {clustering_config_success_migrate_ids}\n"
            "log_clustering_clusteringsubscription: {clustering_subscription_success_migrate_ids}\n"
            "log_clustering_noticegroup: {notice_group_success_migrate_ids}\n"
            "log_clustering_signaturestrategysettings: {signature_strategy_settings_success_migrate_ids}",
            aiops_model_success_migrate_ids=aiops_model_success_migrate_ids,
            aiops_model_experiment_success_migrate_ids=aiops_model_experiment_success_migrate_ids,
            aiops_signature_and_pattern_success_migrate_ids=aiops_signature_and_pattern_success_migrate_ids,
            sample_set_success_migrate_ids=sample_set_success_migrate_ids,
            clustering_remark_success_migrate_ids=clustering_remark_success_migrate_ids,
            regex_template_success_migrate_ids=regex_template_success_migrate_ids,
            index_set_success_migrate_index_set_ids=index_set_success_migrate_index_set_ids,
            index_set_data_success_migrate_index_ids=index_set_data_success_migrate_index_ids,
            collector_config_success_migrate_collector_config_ids=collector_config_success_migrate_collector_config_ids,
            container_collector_config_success_migrate_ids=container_collector_config_success_migrate_ids,
            clustering_config_success_migrate_ids=clustering_config_success_migrate_ids,
            clustering_subscription_success_migrate_ids=clustering_subscription_success_migrate_ids,
            notice_group_success_migrate_ids=notice_group_success_migrate_ids,
            signature_strategy_settings_success_migrate_ids=signature_strategy_settings_success_migrate_ids,
        )

        for collector_config_id, collector_config_name in collector_config_id_name_dict.items():
            try:
                CollectorHandler.get_instance(collector_config_id).start()
            except Exception as e:
                Prompt.error(
                    msg="采集项 [{collector_config_id}] {collector_config_name} 重新启用失败, 错误信息: {error}",
                    collector_config_id=collector_config_id,
                    collector_config_name=collector_config_name,
                    error=str(e),
                )

    @staticmethod
    def file_datas_save_db(model, file_datas):
        if not file_datas:
            return []

        objs = []

        for data in file_datas:
            # 赋值原创建人
            activate_request(generate_request(data.get("created_by", "admin")))
            obj = model.objects.create(**data)
            objs.append(obj)

        return objs

    @staticmethod
    def data_save_db(model, data):
        if not data:
            return None

        # 赋值原创建人
        activate_request(generate_request(data.get("created_by", "admin")))
        obj = model.objects.create(**data)

        return obj

    @staticmethod
    def transform_dict_list_to_customization_key_dict_list_dict(
        key,
        dict_list: list[dict],
        bk_biz_id_set: set[int] = None,
        space_uid_set: set[str] = None,
        index_set_id_set: set[int] = None,
        collector_config_id_set: set[int] = None,
    ) -> dict[str : list[dict]]:
        if not key or not dict_list:
            return {}

        condition = set()
        if bk_biz_id_set:
            condition = bk_biz_id_set
        elif space_uid_set:
            condition = space_uid_set
        elif index_set_id_set:
            condition = index_set_id_set
        elif collector_config_id_set:
            condition = collector_config_id_set

        dict_list_dict = defaultdict(list)

        for item in dict_list:
            value = item.get(key)

            if not value:
                continue

            if condition and value not in condition:
                continue

            dict_list_dict[value].append(item)

        return dict_list_dict

    @staticmethod
    def transform_dict_list_to_customization_key_dict(
        key, dict_list: list[dict], index_set_id_set: set[int] = None
    ) -> dict[str:dict]:
        if not key or not dict_list:
            return {}

        condition = set()
        if index_set_id_set:
            condition = index_set_id_set

        result = {}

        for item in dict_list:
            value = item.get(key)

            if not value:
                continue

            if condition and value not in condition:
                continue

            result[value] = item

        return result

    @staticmethod
    def format_multi_str_split_by_comma_field_back(values_str):
        if values_str:
            # 去除前后 ,
            values_str = values_str.strip(",")
            # 根据 , 分割为列表、去除空值
            no_bulk_values = [value for value in values_str.split(",") if value.strip()]
            # 重新按 , 拼接回字符串
            values_str = ",".join(no_bulk_values)
        else:
            values_str = None

        return values_str
