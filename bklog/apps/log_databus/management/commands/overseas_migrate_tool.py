import json
import os
import traceback
from collections import defaultdict
from typing import Any

from django.core.management import BaseCommand, CommandError
from django.db import transaction

from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.utils.local import activate_request
from apps.utils.thread import generate_request
from bkm_space.utils import bk_biz_id_to_space_uid
from home_application.management.commands.migrate_tool import (
    parse_str_int_list,
    Database,
    JsonFile,
    MigrateStatus,
    Prompt,
)

PROJECT_PATH = os.getcwd()

BK_LOG_SEARCH_OVERSEAS_MIGRATE_RESULT_TABLE = "bk_log_search_overseas_migrate_result_table"


class Command(BaseCommand):
    """海外迁移指令类"""

    def add_arguments(self, parser):
        parser.add_argument("-b", "--bk_biz_id", help="需要导入的业务, 不传时导入所有的业务", type=int, default=0)
        parser.add_argument(
            "--index_set_ids", help="需要导入的索引集 ID, 不传时导入所有的索引集, 例如: 1,2,3", type=str, default=""
        )
        parser.add_argument(
            "-is",
            "--index_set",
            help="需要导入的索引集数据, 默认为: log_search_logindexset.json",
            default=os.path.join(PROJECT_PATH, "log_search_logindexset.json"),
        )
        parser.add_argument(
            "-isd",
            "--index_set_data",
            help="需要导入的索引集审批数据, 默认为: log_search_logindexsetdata.json",
            default=os.path.join(PROJECT_PATH, "log_search_logindexsetdata.json"),
        )
        parser.add_argument(
            "-cc",
            "--collector_config",
            type=str,
            help="需要导入的采集项数据, 默认为: log_databus_collectorconfig.json",
            default=os.path.join(PROJECT_PATH, "log_databus_collectorconfig.json"),
        )
        parser.add_argument(
            "-ccc",
            "--container_collector_config",
            type=str,
            help="需要导入的容器采集项数据, 默认为: log_databus_containercollectorconfig.json",
            default=os.path.join(PROJECT_PATH, "log_databus_containercollectorconfig.json"),
        )
        parser.add_argument("--mysql_host", type=str, help="公共数据库地址", required=True)
        parser.add_argument("--mysql_port", help="公共数据库端口", type=int, default=3306)
        parser.add_argument("--mysql_db", help="公共数据库名称", type=str, required=True)
        parser.add_argument("--mysql_user", help="公共数据库用户", type=str, default="root")
        parser.add_argument("--mysql_password", type=str, help="公共数据库密码", required=True)

    def handle(self, *args, **options):
        json_filepath_dict = {
            "index_set": options["index_set"],
            "index_set_data": options["index_set_data"],
            "collector_config": options["collector_config"],
            "container_collector_config": options["container_collector_config"],
        }

        for json_filepath in json_filepath_dict.values():
            if not os.path.exists(json_filepath):
                raise CommandError(f"json 文件不存在：{json_filepath}")
            if not json_filepath.endswith(".json"):
                raise CommandError(f"文件格式错误(.json)：{json_filepath}")

        mysql_config = {
            "host": options["mysql_host"],
            "port": options["mysql_port"],
            "db": options["mysql_db"],
            "user": options["mysql_user"],
            "password": options["mysql_password"],
        }

        OverseasMigrateTool(
            json_filepath_dict=json_filepath_dict,
            mysql_config=mysql_config,
            bk_biz_id=options["bk_biz_id"],
            index_set_ids_str=options["index_set_ids"],
        ).migrate()


class OverseasMigrateTool:
    """海外迁移工具类"""

    def __init__(
        self,
        json_filepath_dict: dict,
        mysql_config: dict,
        bk_biz_id: int = 0,
        index_set_ids_str: str = "",
    ):
        self.filepath_dict = json_filepath_dict
        self.result_table_name = BK_LOG_SEARCH_OVERSEAS_MIGRATE_RESULT_TABLE
        self.db = Database(**mysql_config)
        self.db.connect()
        self.create_table_if_not_exists()
        self.bk_biz_id = bk_biz_id
        self.space_uid = ""
        if self.bk_biz_id:
            self.space_uid = bk_biz_id_to_space_uid(self.bk_biz_id)
        self.index_set_ids_set = set(parse_str_int_list(index_set_ids_str))

    def create_table_if_not_exists(self) -> None:
        """创建日志平台海外迁移结果表"""
        sql = f"""
            CREATE TABLE IF NOT EXISTS `{self.result_table_name}` (
                `id` int NOT NULL AUTO_INCREMENT COMMENT 'ID',
                `bk_biz_id` int NOT NULL COMMENT '业务 ID（迁移前后不变）',
                `space_uid` varchar(255) NOT NULL COMMENT '蓝鲸空间 UID（迁移前后不变）',
                `index_set_id` int NOT NULL COMMENT '索引集 ID（迁移前后不变）',
                `origin_collector_config_id` int COMMENT '原采集项 ID（旧环境）',
                `collector_config_id` int COMMENT '新采集项ID（新环境）',
                `status` varchar(32) NOT NULL COMMENT '迁移状态',
                `details` text NOT NULL COMMENT '迁移详情',
                PRIMARY KEY (`id`)
            ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='日志平台海外迁移结果表';
        """
        self.db.execute_sql(sql)

    @transaction.atomic
    def migrate(self):
        """
        原数据迁移
        """
        # 获取文件路径
        index_set_filepath = self.filepath_dict.get("index_set")
        index_set_data_filepath = self.filepath_dict.get("index_set_data")
        collector_config_filepath = self.filepath_dict.get("collector_config")
        container_collector_config_filepath = self.filepath_dict.get("container_collector_config")

        # 获取文件数据
        index_set_file_datas = JsonFile.read(index_set_filepath)
        index_set_data_file_datas = JsonFile.read(index_set_data_filepath)
        collector_config_file_datas = JsonFile.read(collector_config_filepath)
        container_collector_config_file_datas = JsonFile.read(container_collector_config_filepath)

        # 创建数据字典，方便后续取值
        index_set_data_file_data_dict = defaultdict(list)
        [index_set_data_file_data_dict[data["index_set_id"]].append(data) for data in index_set_data_file_datas]
        collector_config_file_data_dict = {data.get("index_set_id"): data for data in collector_config_file_datas}
        container_collector_config_file_data_dict = defaultdict(list)
        [
            container_collector_config_file_data_dict[data["collector_config_id"]].append(data)
            for data in container_collector_config_file_datas
        ]

        collector_config_id_name_dict = {}

        # 遍历索引集数据，进行迁移操作
        for data in index_set_file_datas:
            if self.bk_biz_id and (
                data.get("space_uid") != self.space_uid or data.get("index_set_id") not in self.index_set_ids_set
            ):
                continue

            index_set_id = data.get("index_set_id")

            # 构建初始迁移记录
            migrate_record = {
                "bk_biz_id": data.get("bk_biz_id"),
                "space_uid": data.get("space_uid"),
                "index_set_id": index_set_id,
            }

            try:
                # 赋值原创建人
                activate_request(generate_request(data["created_by"]))

                # 通过字典取出与 index_set_id 关联的其他表数据
                index_set_data_datas = index_set_data_file_data_dict.get(index_set_id, [])
                collector_config_data = collector_config_file_data_dict.get(index_set_id, {})

                if collector_config_data:
                    collector_config_id = collector_config_data.get("collector_config_id")

                    collector_config_id_name_dict[collector_config_id] = collector_config_data.get(
                        "collector_config_name"
                    )

                    container_collector_config_datas = container_collector_config_file_data_dict.get(
                        collector_config_id, []
                    )

                    migrate_record["origin_collector_config_id"] = collector_config_id
                    migrate_record["collector_config_id"] = collector_config_id

                    index_set_data_creates = [LogIndexSetData(**item) for item in index_set_data_datas]
                    container_collector_config_creates = [
                        ContainerCollectorConfig(**item) for item in container_collector_config_datas
                    ]

                    LogIndexSet.objects.create(**data)

                    # 插入与 index_set_id 关联的其他表数据
                    log_index_set_data_objs = []
                    if index_set_data_creates:
                        log_index_set_data_objs = LogIndexSetData.objects.bulk_create(index_set_data_creates)

                    container_collector_config_objs = []
                    if container_collector_config_creates:
                        container_collector_config_objs = ContainerCollectorConfig.objects.bulk_create(
                            container_collector_config_creates
                        )

                    details = json.dumps(
                        {
                            "log_index_set_data_ids": [item.id for item in log_index_set_data_objs],
                            "container_collector_config_ids": [item.id for item in container_collector_config_objs],
                        }
                    )
                    migrate_record.update({"status": MigrateStatus.SUCCESS, "details": details})
                else:
                    index_set_data_creates = [LogIndexSetData(**item) for item in index_set_data_datas]

                    LogIndexSet.objects.create(**data)

                    # 插入与 index_set_id 关联的其他表数据
                    log_index_set_data_objs = []
                    if index_set_data_creates:
                        log_index_set_data_objs = LogIndexSetData.objects.bulk_create(index_set_data_creates)

                    details = json.dumps(
                        {
                            "log_index_set_data_ids": [item.id for item in log_index_set_data_objs],
                        }
                    )
                    migrate_record.update({"status": MigrateStatus.SUCCESS, "details": details})

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

                self.record(migrate_record)

        activate_request(generate_request("admin"))
        self.db.close()

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

    @transaction.atomic
    def remove_id_except_index_set_id_migrate(self):
        """
        除了 index_set_id, 其他 id 全部清除进行迁移, 自动生成新 id
        """
        # 获取文件路径
        index_set_filepath = self.filepath_dict.get("index_set")
        index_set_data_filepath = self.filepath_dict.get("index_set_data")
        collector_config_filepath = self.filepath_dict.get("collector_config")
        container_collector_config_filepath = self.filepath_dict.get("container_collector_config")

        # 获取文件数据
        index_set_file_datas = JsonFile.read(index_set_filepath)
        index_set_data_file_datas = JsonFile.read(index_set_data_filepath)
        collector_config_file_datas = JsonFile.read(collector_config_filepath)
        container_collector_config_file_datas = JsonFile.read(container_collector_config_filepath)

        # 创建数据字典，方便后续取值
        index_set_data_file_data_dict = defaultdict(list)
        collector_config_file_data_dict = {data.get("index_set_id"): data for data in collector_config_file_datas}
        container_collector_config_file_data_dict = defaultdict(list)

        [index_set_data_file_data_dict[data["index_set_id"]].append(data) for data in index_set_data_file_datas]
        [
            container_collector_config_file_data_dict[data["collector_config_id"]].append(data)
            for data in container_collector_config_file_datas
        ]

        # 遍历索引集数据，进行迁移操作
        for data in index_set_file_datas:
            if self.bk_biz_id and (
                data.get("space_uid") != self.space_uid or data.get("index_set_id") not in self.index_set_ids_set
            ):
                continue

            index_set_id = data.get("index_set_id")

            # 构建初始迁移记录
            migrate_record = {
                "bk_biz_id": data.get("bk_biz_id"),
                "space_uid": data.get("space_uid"),
                "index_set_id": index_set_id,
            }

            try:
                # 赋值原创建人
                activate_request(generate_request(data["created_by"]))

                # 通过字典取出与 index_set_id 关联的其他表数据
                index_set_data_datas = index_set_data_file_data_dict.get(index_set_id, [])
                collector_config_data = collector_config_file_data_dict.get(index_set_id, {})

                if collector_config_data:
                    origin_collector_config_id = collector_config_data.pop("collector_config_id", None)

                    container_collector_config_datas = container_collector_config_file_data_dict.get(
                        origin_collector_config_id, []
                    )

                    migrate_record["origin_collector_config_id"] = origin_collector_config_id

                    # 插入 collector_config 表数据，获取新 collector_config_id
                    collector_config_obj = CollectorConfig.objects.create(**collector_config_data)
                    collector_config_id = collector_config_obj.collector_config_id

                    migrate_record["collector_config_id"] = collector_config_id

                    # 更新 collector_config_id
                    data["collector_config_id"] = collector_config_id

                    index_set_data_creates = []
                    for item in index_set_data_datas:
                        item.pop("id", None)
                        index_set_data_creates.append(LogIndexSetData(**item))

                    container_collector_config_creates = []
                    for item in container_collector_config_datas:
                        item.pop("id", None)
                        item["collector_config_id"] = collector_config_id
                        container_collector_config_creates.append(ContainerCollectorConfig(**item))

                    LogIndexSet.objects.create(**data)

                    # 插入与 index_set_id 关联的其他表数据
                    log_index_set_data_objs = []
                    if index_set_data_creates:
                        log_index_set_data_objs = LogIndexSetData.objects.bulk_create(index_set_data_creates)

                    container_collector_config_objs = []
                    if container_collector_config_creates:
                        container_collector_config_objs = ContainerCollectorConfig.objects.bulk_create(
                            container_collector_config_creates
                        )

                    details = json.dumps(
                        {
                            "log_index_set_data_ids": [item.id for item in log_index_set_data_objs],
                            "container_collector_config_ids": [item.id for item in container_collector_config_objs],
                        }
                    )
                    migrate_record.update({"status": MigrateStatus.SUCCESS, "details": details})
                else:
                    index_set_data_creates = []
                    for item in index_set_data_datas:
                        item.pop("id", None)
                        index_set_data_creates.append(LogIndexSetData(**item))

                    LogIndexSet.objects.create(**data)

                    # 插入与 index_set_id 关联的其他表数据
                    log_index_set_data_objs = []
                    if index_set_data_creates:
                        log_index_set_data_objs = LogIndexSetData.objects.bulk_create(index_set_data_creates)

                    details = json.dumps(
                        {
                            "log_index_set_data_ids": [item.id for item in log_index_set_data_objs],
                        }
                    )
                    migrate_record.update({"status": MigrateStatus.SUCCESS, "details": details})

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

                self.record(migrate_record)

        activate_request(generate_request("admin"))
        self.db.close()

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

    def record(self, migrate_record: dict[str, Any]) -> None:
        """
        记录海外迁移结果
        """
        self.db.insert(table_name=self.result_table_name, data=migrate_record)
