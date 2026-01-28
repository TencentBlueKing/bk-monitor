import json
import os
import traceback
from collections import defaultdict
from typing import Any

from django.core.management import BaseCommand, CommandError
from django.db import transaction

from apps.log_clustering.models import (
    AiopsModel,
    AiopsModelExperiment,
    AiopsSignatureAndPattern,
    SampleSet,
    RegexTemplate,
    ClusteringRemark,
)
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.utils.local import activate_request
from apps.utils.thread import generate_request
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id
from home_application.management.commands.migrate_tool import (
    parse_str_int_list,
    JsonFile,
    MigrateStatus,
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
            bk_biz_id=options["bk_biz_id"],
            index_set_ids_str=options["index_set_ids"],
        ).migrate()


class OverseasMigrateTool:
    """海外迁移工具类"""

    def __init__(
        self,
        json_content_dict: dict,
        bk_biz_id: int = 0,
        index_set_ids_str: str = "",
    ):
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

        if self.index_set_id_set and index_set_id_set:
            self.index_set_id_set = self.index_set_id_set & index_set_id_set
        elif not self.index_set_id_set and index_set_id_set:
            self.index_set_id_set = index_set_id_set

        # 无外键关联, 直接迁移
        self.file_datas_save_db(AiopsModel, self.json_content_dict.get("aiops_model", []))
        self.file_datas_save_db(AiopsModelExperiment, self.json_content_dict.get("aiops_model_experiment", []))
        self.file_datas_save_db(AiopsSignatureAndPattern, self.json_content_dict.get("aiops_signature_and_pattern", []))
        self.file_datas_save_db(SampleSet, self.json_content_dict.get("sample_set", []))

        # 有外键关联, 需关联迁移
        # 创建数据字典，方便后续取值
        regex_template_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "space_uid",
            self.json_content_dict.get("regex_template", []),
            space_uid_set={self.space_uid} if self.space_uid else None,
        )
        clustering_remark_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "bk_biz_id",
            self.json_content_dict.get("clustering_remark", []),
            bk_biz_id_set={self.bk_biz_id} if self.bk_biz_id else None,
        )
        index_set_data_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
            "index_set_id",
            self.json_content_dict.get("index_set_data", []),
            index_set_id_set=self.index_set_id_set if self.index_set_id_set else None,
        )
        collector_config_file_data_dict = {
            data.get("index_set_id"): data for data in self.json_content_dict.get("collector_config", [])
        }
        # clustering_config_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
        #     "index_set_id",
        #     self.json_content_dict.get("clustering_config", []),
        #     index_set_id_set=self.index_set_id_set if self.index_set_id_set else None
        # )
        # clustering_subscription_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
        #     "index_set_id",
        #     self.json_content_dict.get("clustering_subscription", []),
        #     index_set_id_set=self.index_set_id_set if self.index_set_id_set else None
        # )
        # notice_group_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
        #     "index_set_id",
        #     self.json_content_dict.get("notice_group", []),
        #     index_set_id_set=self.index_set_id_set if self.index_set_id_set else None
        # )
        # signature_strategy_settings_file_datas_dict = self.transform_dict_list_to_customization_key_dict_list_dict(
        #     "index_set_id",
        #     self.json_content_dict.get("signature_strategy_settings", []),
        #     index_set_id_set=self.index_set_id_set if self.index_set_id_set else None
        # )

        regex_template_file_datas = []
        clustering_remark_file_datas = []
        if self.bk_biz_id and self.space_uid:
            regex_template_file_datas = regex_template_file_datas_dict.get(self.space_uid, [])
            clustering_remark_file_datas = clustering_remark_file_datas_dict.get(self.space_uid, [])
        else:
            for value in regex_template_file_datas_dict.values():
                regex_template_file_datas.extend(value)
            for value in clustering_remark_file_datas_dict.values():
                clustering_remark_file_datas.extend(value)

        self.file_datas_save_db(RegexTemplate, regex_template_file_datas)
        self.file_datas_save_db(ClusteringRemark, clustering_remark_file_datas)

        collector_config_id_name_dict = {}

        # 遍历索引集数据，进行迁移操作
        for data in index_set_file_datas:
            if (self.bk_biz_id and data.get("space_uid") != self.space_uid) or (
                self.index_set_id_set and data.get("index_set_id") not in self.index_set_id_set
            ):
                continue

            index_set_id = data.get("index_set_id")
            space_uid = data.get("space_uid", "")
            bk_biz_id = space_uid_to_bk_biz_id(space_uid)

            # 构建初始迁移记录
            migrate_record = {
                "bk_biz_id": bk_biz_id,
                "space_uid": space_uid,
                "index_set_id": index_set_id,
            }

            # 格式化数据为原格式
            data["tag_ids"] = self.format_multi_str_split_by_comma_field_back(data.get("tag_ids", ""))
            data["view_roles"] = self.format_multi_str_split_by_comma_field_back(data.get("view_roles", ""))

            try:
                # 赋值原创建人
                activate_request(generate_request(data["created_by"]))

                # 通过字典取出与 index_set_id 关联的其他表数据
                index_set_data_datas = index_set_data_file_datas_dict.get(index_set_id, [])
                collector_config_data = collector_config_file_data_dict.get(index_set_id, {})

                details = {}

                if collector_config_data:
                    collector_config_id = collector_config_data.get("collector_config_id")

                    collector_config_id_name_dict[collector_config_id] = collector_config_data.get(
                        "collector_config_name"
                    )

                    migrate_record["origin_collector_config_id"] = collector_config_id
                    migrate_record["collector_config_id"] = collector_config_id

                    container_collector_config_file_datas_dict = (
                        self.transform_dict_list_to_customization_key_dict_list_dict(
                            "collector_config_id",
                            self.json_content_dict.get("container_collector_config", []),
                            collector_config_id_set={collector_config_id} if collector_config_id else None,
                        )
                    )
                    # 格式化为 task_id_list 原格式
                    collector_config_data["task_id_list"] = self.format_multi_str_split_by_comma_field_back(
                        collector_config_data.get("task_id_list", "")
                    )

                    CollectorConfig.objects.create(**collector_config_data)

                    container_collector_config_datas = container_collector_config_file_datas_dict.get(
                        collector_config_id, []
                    )

                    container_collector_config_objs = self.file_datas_save_db(
                        ContainerCollectorConfig, container_collector_config_datas
                    )

                    details["container_collector_config_ids"] = [item.id for item in container_collector_config_objs]

                LogIndexSet.objects.create(**data)

                index_set_data_objs = self.file_datas_save_db(LogIndexSetData, index_set_data_datas)

                details["index_set_data_index_ids"] = [item.index_id for item in index_set_data_objs]

                migrate_record.update({"status": MigrateStatus.SUCCESS, "details": json.dumps(details)})

            except Exception as e:
                details = json.dumps(
                    {
                        "exception": str(e),
                        "traceback": traceback.format_exc(),
                    }
                )
                migrate_record.update({"status": MigrateStatus.FAIL, "details": details})
                self.fail(data=data, migrate_record=migrate_record)
            finally:
                migrate_record.setdefault("bk_biz_id", 0)
                migrate_record.setdefault("space_uid", "")
                migrate_record.setdefault("index_set_id", 0)
                migrate_record.setdefault("status", MigrateStatus.FAIL)
                migrate_record.setdefault("details", json.dumps({"error": "unknown error"}))

                # try:
                #     self.record(migrate_record)
                # except Exception as e:
                #     Prompt.error(
                #         msg="迁移操作记录失败, 索引集 ID: {index_set_id}, 错误信息: {error}",
                #         index_set_id=index_set_id,
                #         error=str(e),
                #     )

        activate_request(generate_request("admin"))
        # self.db.close()

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
            return

        objs = [model(**data) for data in file_datas]

        return model.objects.bulk_create(objs)

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

    @staticmethod
    def fail(data: dict[str, Any], migrate_record: dict[str, Any]) -> None:
        """
        打印迁移失败日志
        """
        Prompt.error(
            msg="索引集 [{index_set_id}] {index_set_name} 迁移失败, 错误信息: {error}",
            index_set_id=data.get("index_set_id", "no index set id"),
            index_set_name=data.get("index_set_name", "no index set name"),
            error=migrate_record["details"],
        )
