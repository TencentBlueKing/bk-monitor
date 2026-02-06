import os
from collections import defaultdict

from django.core.management import BaseCommand, CommandError
from django.db import transaction, IntegrityError
from django.forms import model_to_dict

from apps.api import OverseasMigrateApi
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
from apps.log_databus.management.commands.export_table_data_json_tool import str_to_bool
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
            "--is_first_execute",
            type=str_to_bool,
            help="该环境下是否第一次执行此迁移指令, 例如: True/False、1/0、yes/no、y/n",
            required=True,
        )
        parser.add_argument(
            "--is_skip",
            type=str_to_bool,
            help="跳过 log_clustering_clusteringremark、log_clustering_regextemplate 表迁移",
            default=False,
        )
        parser.add_argument(
            "-mi",
            "--is_migrate_index_set",
            type=str_to_bool,
            help="是否迁移索引集相关表",
            default=True,
        )
        parser.add_argument(
            "-mc",
            "--is_migrate_clustering",
            type=str_to_bool,
            help="是否迁移日志聚类相关表",
            default=True,
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
            is_first_execute=options["is_first_execute"],
            is_skip=options["is_skip"],
            is_migrate_index_set=options["is_migrate_index_set"],
            is_migrate_clustering=options["is_migrate_clustering"],
            json_content_dict=json_content_dict,
            bk_biz_id=options["bk_biz_id"],
            index_set_ids_str=options["index_set_ids"],
        ).migrate()


class OverseasMigrateTool:
    """海外迁移工具类"""

    def __init__(
        self,
        is_first_execute: bool,
        is_skip: bool,
        is_migrate_index_set: bool,
        is_migrate_clustering: bool,
        json_content_dict: dict,
        bk_biz_id: int = 0,
        index_set_ids_str: str = "",
    ):
        self.is_first_execute = is_first_execute
        self.is_skip = is_skip
        self.is_migrate_index_set = is_migrate_index_set
        self.is_migrate_clustering = is_migrate_clustering
        self.json_content_dict = json_content_dict
        self.bk_biz_id = bk_biz_id
        self.space_uid = ""
        if self.bk_biz_id:
            self.space_uid = bk_biz_id_to_space_uid(self.bk_biz_id)
        self.index_set_id_set = set(parse_str_int_list(index_set_ids_str))

        # 记录每张表成功迁移的 ID
        self.aiops_model_success_migrate_ids = []
        self.aiops_model_experiment_success_migrate_ids = []
        self.aiops_signature_and_pattern_success_migrate_ids = []
        self.sample_set_success_migrate_ids = []
        self.clustering_remark_success_migrate_ids = []
        self.regex_template_success_migrate_ids = []
        self.index_set_success_migrate_index_set_ids = []
        self.index_set_data_success_migrate_index_ids = []
        self.collector_config_success_migrate_collector_config_ids = []
        self.container_collector_config_success_migrate_ids = []
        self.clustering_config_success_migrate_ids = []
        self.clustering_subscription_success_migrate_ids = []
        self.notice_group_success_migrate_ids = []
        self.signature_strategy_settings_success_migrate_ids = []

    @transaction.atomic
    def migrate(self):
        """
        原数据迁移
        """
        index_set_file_datas = self.json_content_dict.get("index_set", [])
        if not self.index_set_id_set:
            if self.space_uid:
                index_set_file_datas = [
                    data for data in index_set_file_datas if data.get("space_uid", "") == self.space_uid
                ]
            self.index_set_id_set = set(
                [data.get("index_set_id") for data in index_set_file_datas if data.get("index_set_id")]
            )

        with transaction.atomic():
            # 无外键关联, 直接全表迁移
            try:
                aiops_model_objs = self.datas_save_db(AiopsModel, self.json_content_dict.get("aiops_model", []))
                aiops_model_experiment_objs = self.datas_save_db(
                    AiopsModelExperiment, self.json_content_dict.get("aiops_model_experiment", [])
                )
                aiops_signature_and_pattern_objs = self.datas_save_db(
                    AiopsSignatureAndPattern, self.json_content_dict.get("aiops_signature_and_pattern", [])
                )
                sample_set_objs = self.datas_save_db(SampleSet, self.json_content_dict.get("sample_set", []))

                self.aiops_model_success_migrate_ids = [obj["id"] for obj in aiops_model_objs]
                self.aiops_model_experiment_success_migrate_ids = [obj["id"] for obj in aiops_model_experiment_objs]
                self.aiops_signature_and_pattern_success_migrate_ids = [
                    obj["id"] for obj in aiops_signature_and_pattern_objs
                ]
                self.sample_set_success_migrate_ids = [obj["id"] for obj in sample_set_objs]
            except IntegrityError as e:
                if self.is_first_execute:
                    raise CommandError(
                        "\n此报错原因可能为: "
                        "\n1.该环境下不是第一次执行此迁移指令, 表 log_clustering_aiopsmodel、log_clustering_aiopsmodelexperiment、log_clustering_aiopssignatureandpattern、log_clustering_sampleset 已迁移过所有的数据"
                        "\n请增加参数 --is_first_execute False 尝试解决\n"
                    ) from e
                else:
                    Prompt.info(
                        msg="跳过表 log_clustering_aiopsmodel、log_clustering_aiopsmodelexperiment、log_clustering_aiopssignatureandpattern、log_clustering_sampleset 的迁移操作\n"
                    )
            except Exception as e:
                raise Exception(
                    f"\n表 log_clustering_aiopsmodel、log_clustering_aiopsmodelexperiment、log_clustering_aiopssignatureandpattern、log_clustering_sampleset 迁移时发生未知错误: {str(e)}\n"
                ) from e

        with transaction.atomic():
            # 有外键关联, 需关联迁移
            # 创建数据字典，方便后续取值
            clustering_remark_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
                "bk_biz_id",
                self.json_content_dict.get("clustering_remark", []),
                {self.bk_biz_id} if self.bk_biz_id else set(),
            )
            regex_template_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
                "space_uid",
                self.json_content_dict.get("regex_template", []),
                {self.space_uid} if self.space_uid else set(),
            )

            # 参数 bk_biz_id 有值则进行关联迁移, 否则全表迁移
            try:
                clustering_remark_file_datas = []
                regex_template_file_datas = []

                for value in clustering_remark_file_datas_dict.values():
                    clustering_remark_file_datas.extend(value)
                for value in regex_template_file_datas_dict.values():
                    regex_template_file_datas.extend(value)

                clustering_remark_objs = self.datas_save_db(ClusteringRemark, clustering_remark_file_datas)
                regex_template_objs = self.datas_save_db(RegexTemplate, regex_template_file_datas)

                self.clustering_remark_success_migrate_ids = [obj["id"] for obj in clustering_remark_objs]
                self.regex_template_success_migrate_ids = [obj["id"] for obj in regex_template_objs]
            except IntegrityError as e:
                if not self.is_skip:
                    raise CommandError(
                        f"\n此报错原因可能为: "
                        f"\n1.表 log_clustering_clusteringremark、log_clustering_regextemplate 已迁移过 bk_biz_id 为 {self.bk_biz_id} 的数据"
                        f"\n2.表 log_clustering_clusteringremark、log_clustering_regextemplate 已迁移过所有的数据"
                        f"\n请增加参数 --is_skip True 尝试解决\n"
                    ) from e
                else:
                    Prompt.info(msg="跳过表 log_clustering_clusteringremark、log_clustering_regextemplate 的迁移操作\n")
            except Exception as e:
                raise Exception(
                    f"表 log_clustering_clusteringremark、log_clustering_regextemplate 迁移时发生未知错误: {str(e)}\n"
                ) from e

        collector_config_id_name_dict = {}

        if self.is_migrate_index_set:
            # 迁移索引集相关表
            collector_config_id_name_dict = self.migrate_index_set(index_set_file_datas)

        if self.is_migrate_clustering:
            # 迁移日志聚类相关表
            self.migrate_clustering()

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
            aiops_model_success_migrate_ids=self.aiops_model_success_migrate_ids,
            aiops_model_experiment_success_migrate_ids=self.aiops_model_experiment_success_migrate_ids,
            aiops_signature_and_pattern_success_migrate_ids=self.aiops_signature_and_pattern_success_migrate_ids,
            sample_set_success_migrate_ids=self.sample_set_success_migrate_ids,
            clustering_remark_success_migrate_ids=self.clustering_remark_success_migrate_ids,
            regex_template_success_migrate_ids=self.regex_template_success_migrate_ids,
            index_set_success_migrate_index_set_ids=self.index_set_success_migrate_index_set_ids,
            index_set_data_success_migrate_index_ids=self.index_set_data_success_migrate_index_ids,
            collector_config_success_migrate_collector_config_ids=self.collector_config_success_migrate_collector_config_ids,
            container_collector_config_success_migrate_ids=self.container_collector_config_success_migrate_ids,
            clustering_config_success_migrate_ids=self.clustering_config_success_migrate_ids,
            clustering_subscription_success_migrate_ids=self.clustering_subscription_success_migrate_ids,
            notice_group_success_migrate_ids=self.notice_group_success_migrate_ids,
            signature_strategy_settings_success_migrate_ids=self.signature_strategy_settings_success_migrate_ids,
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

    def migrate_index_set(self, index_set_file_datas: list[dict]) -> dict:
        """
        迁移索引集相关表
        """
        # 创建数据字典，方便后续取值
        index_set_data_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id", self.json_content_dict.get("index_set_data", []), self.index_set_id_set
        )
        collector_config_file_data_dict = self.transform_dict_list_to_customization_key_dict(
            "index_set_id", self.json_content_dict.get("collector_config", []), self.index_set_id_set
        )

        collector_config_id_name_dict = {}

        # 遍历索引集数据，进行关联迁移操作
        for data in index_set_file_datas:
            if (self.bk_biz_id and data.get("space_uid") != self.space_uid) or (
                self.index_set_id_set and data.get("index_set_id") not in self.index_set_id_set
            ):
                continue

            index_set_id = data.get("index_set_id")

            # 格式化数据为原格式
            data["tag_ids"] = self.format_multi_str_split_by_comma_field_back(data.get("tag_ids", ""))
            data["view_roles"] = self.format_multi_str_split_by_comma_field_back(data.get("view_roles", ""))

            # 通过 index_set_id 取出表数据
            index_set_data_datas = index_set_data_file_datas_dict.get(index_set_id, [])
            collector_config_data = collector_config_file_data_dict.get(index_set_id, {})

            if collector_config_data:
                collector_config_id = collector_config_data.get("collector_config_id")

                collector_config_id_name_dict[collector_config_id] = collector_config_data.get("collector_config_name")

                container_collector_config_file_datas_dict = (
                    self.transform_dict_list_to_customization_key_dict_list_dict(
                        "collector_config_id",
                        self.json_content_dict.get("container_collector_config", []),
                        {collector_config_id},
                    )
                )
                # 通过 collector_config_id 取出表数据
                container_collector_config_datas = container_collector_config_file_datas_dict.get(
                    collector_config_id, []
                )

                # 格式化为 task_id_list 原格式
                collector_config_data["task_id_list"] = self.format_multi_str_split_by_comma_field_back(
                    collector_config_data.get("task_id_list", "")
                )

                collector_config_obj = self.data_save_db(CollectorConfig, collector_config_data)
                self.collector_config_success_migrate_collector_config_ids.append(
                    collector_config_obj["collector_config_id"]
                )

                container_collector_config_objs = self.datas_save_db(
                    ContainerCollectorConfig, container_collector_config_datas
                )
                self.container_collector_config_success_migrate_ids.extend(
                    [obj["id"] for obj in container_collector_config_objs]
                )

            index_set_obj = self.data_save_db(LogIndexSet, data)
            self.index_set_success_migrate_index_set_ids.append(index_set_obj["index_set_id"])

            index_set_data_objs = self.datas_save_db(LogIndexSetData, index_set_data_datas)
            self.index_set_data_success_migrate_index_ids.extend([obj["index_id"] for obj in index_set_data_objs])

        return collector_config_id_name_dict

    def migrate_clustering(self):
        """
        迁移日志聚类相关表
        """
        try:
            # 获取 flow_id 映射信息
            result = OverseasMigrateApi.get_migration_mapping_info()
            flow_id_mapping_info_dict = result.get("flow_mapping_info", {})
        except Exception as e:
            Prompt.error(
                msg="获取 flow_id 映射信息失败, 跳过日志聚类相关表的迁移操作, 错误信息: \n{error}", error=str(e)
            )
            return

        clustering_config_file_datas = self.json_content_dict.get("clustering_config", [])

        # 创建数据字典，方便后续取值
        clustering_subscription_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id",
            self.json_content_dict.get("clustering_subscription", []),
            self.index_set_id_set,
        )
        notice_group_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id", self.json_content_dict.get("notice_group", []), self.index_set_id_set
        )
        signature_strategy_settings_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id",
            self.json_content_dict.get("signature_strategy_settings", []),
            self.index_set_id_set,
        )

        # 遍历日志聚类配置，进行关联迁移操作
        for data in clustering_config_file_datas:
            if (self.bk_biz_id and data.get("bk_biz_id") != self.bk_biz_id) or (
                self.index_set_id_set and data.get("index_set_id") not in self.index_set_id_set
            ):
                continue

            index_set_id = data.get("index_set_id")

            # 通过 index_set_id 取出表数据
            clustering_subscription_datas = clustering_subscription_file_datas_dict.get(index_set_id, [])
            notice_group_datas = notice_group_file_datas_dict.get(index_set_id, [])
            signature_strategy_settings_datas = signature_strategy_settings_file_datas_dict.get(index_set_id, [])

            # flow_id 替换为新
            after_treat_flow_id = str(data.get("after_treat_flow_id"))
            pre_treat_flow_id = str(data.get("pre_treat_flow_id"))
            predict_flow_id = str(data.get("predict_flow_id"))
            log_count_aggregation_flow_id = str(data.get("log_count_aggregation_flow_id"))

            if after_treat_flow_id and after_treat_flow_id in flow_id_mapping_info_dict:
                data["after_treat_flow_id"] = flow_id_mapping_info_dict[after_treat_flow_id]

            if pre_treat_flow_id and pre_treat_flow_id in flow_id_mapping_info_dict:
                data["pre_treat_flow_id"] = flow_id_mapping_info_dict[pre_treat_flow_id]

            if predict_flow_id and predict_flow_id in flow_id_mapping_info_dict:
                data["predict_flow_id"] = flow_id_mapping_info_dict[predict_flow_id]

            if log_count_aggregation_flow_id and log_count_aggregation_flow_id in flow_id_mapping_info_dict:
                data["log_count_aggregation_flow_id"] = flow_id_mapping_info_dict[log_count_aggregation_flow_id]

            clustering_config_obj = self.data_save_db(ClusteringConfig, data)
            self.clustering_config_success_migrate_ids.append(clustering_config_obj["id"])

            clustering_subscription_objs = self.datas_save_db(ClusteringSubscription, clustering_subscription_datas)
            self.clustering_subscription_success_migrate_ids.extend([obj["id"] for obj in clustering_subscription_objs])

            notice_group_objs = self.datas_save_db(NoticeGroup, notice_group_datas)
            self.notice_group_success_migrate_ids.extend([obj["id"] for obj in notice_group_objs])

            signature_strategy_settings_objs = self.datas_save_db(
                SignatureStrategySettings, signature_strategy_settings_datas
            )
            self.signature_strategy_settings_success_migrate_ids.extend(
                [obj["id"] for obj in signature_strategy_settings_objs]
            )

    @staticmethod
    def datas_save_db(model, file_datas):
        """
        数据库批量创建, 保留原始创建人, 返回数据库实例字典列表
        """
        if not file_datas:
            return []

        objs = []

        for data in file_datas:
            # 赋值原创建人
            activate_request(generate_request(data.get("created_by", "admin")))
            obj = model.objects.create(**data)
            obj_dict = model_to_dict(obj)
            objs.append(obj_dict)

        return objs

    @staticmethod
    def data_save_db(model, data):
        """
        数据库创建, 保留原始创建人, 返回数据库实例字典
        """
        if not data:
            return None

        # 赋值原创建人
        activate_request(generate_request(data.get("created_by", "admin")))
        obj = model.objects.create(**data)

        return model_to_dict(obj)

    @staticmethod
    def transform_dict_list_to_customization_key_dict_list_dict(
        key,
        dict_list: list[dict],
        condition: set[int | str] = None,
    ) -> dict[str : list[dict]]:
        if not key or not dict_list:
            return {}

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
        key, dict_list: list[dict], condition: set[int | str] = None
    ) -> dict[str:dict]:
        if not key or not dict_list:
            return {}

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
