import json
import os
from datetime import datetime, date

from django.core.management import BaseCommand, CommandError
from django.db import connection, DatabaseError

from bkm_space.utils import bk_biz_id_to_space_uid
from home_application.management.commands.migrate_tool import parse_str_int_list, Prompt, parse_str_list

PROJECT_PATH = os.getcwd()


class Command(BaseCommand):
    """海外迁移指令类"""

    def add_arguments(self, parser):
        parser.add_argument("-b", "--bk_biz_id", help="需要导出的业务, 不传时导出所有的业务", type=int, default=0)
        parser.add_argument(
            "--index_set_ids", help="需要导出的索引集 ID, 不传时导出所有的索引集, 例如: 1,2,3", type=str, default=""
        )
        parser.add_argument("-p", "--path", help="导出文件保存目录, 默认为根目录", type=str, default=PROJECT_PATH)
        parser.add_argument("-om", "--overseas_migrate", help="海外数据迁移", type=bool, default=False)
        parser.add_argument(
            "--table_names",
            help="需要导出的表名, 例如: log_search_logindexset,log_search_logindexsetdata",
            default=None,
        )

    def handle(self, *args, **options):
        is_overseas_migrate = options["overseas_migrate"]
        table_names = options["table_names"]

        if (not is_overseas_migrate and not table_names) or (is_overseas_migrate and table_names):
            raise CommandError("参数错误: --overseas_migrate(-om), --table_names 二选一传入")

        if is_overseas_migrate:
            table_names_str = (
                "log_search_logindexset,"
                "log_search_logindexsetdata,"
                "log_databus_collectorconfig,"
                "log_databus_containercollectorconfig,"
                "log_clustering_aiopsmodel,"
                "log_clustering_aiopsmodelexperiment,"
                "log_clustering_aiopssignatureandpattern,"
                "log_clustering_sampleset,"
                "log_clustering_clusteringconfig,"
                "log_clustering_clusteringremark,"
                "log_clustering_clusteringsubscription,"
                "log_clustering_noticegroup,"
                "log_clustering_regextemplate,"
                "log_clustering_signaturestrategysettings"
            )
        else:
            table_names_str = options["table_names"]

        ExportTableDataJsonTool(
            save_path=options["path"],
            table_names_str=table_names_str,
            bk_biz_id=options["bk_biz_id"],
            index_set_ids_str=options["index_set_ids"],
        ).batch_export()


class ExportTableDataJsonTool:
    def __init__(
        self,
        save_path: str,
        table_names_str: str,
        bk_biz_id: int = 0,
        index_set_ids_str: str = "",
    ):
        self.save_path = save_path
        self.table_names_set = set(parse_str_list(table_names_str))
        self.bk_biz_id = bk_biz_id
        self.space_uid = ""
        if self.bk_biz_id:
            self.space_uid = bk_biz_id_to_space_uid(self.bk_biz_id)
        self.index_set_ids_set = set(parse_str_int_list(index_set_ids_str))

    def batch_export(self):
        """
        批量导出
        """
        query_condition_dict = {}
        query_fields = []

        if self.bk_biz_id:
            query_fields.append("bk_biz_id")
            query_condition_dict["bk_biz_id"] = {
                "operator": "eq",
                "condition": "bk_biz_id = %s",
                "param": self.bk_biz_id,
            }

        if self.space_uid:
            query_fields.append("space_uid")
            query_condition_dict["space_uid"] = {
                "operator": "eq",
                "condition": "space_uid = %s",
                "param": self.space_uid,
            }

        if self.index_set_ids_set:
            query_fields.append("index_set_id")
            placeholders = ", ".join(["%s"] * len(self.index_set_ids_set))
            query_condition_dict["index_set_id"] = {
                "operator": "in",
                "condition": f"index_set_id IN ({placeholders})",
                "param": list(self.index_set_ids_set),
            }

        for table_name in self.table_names_set:
            table_fields = set()
            json_fields = []
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"DESCRIBE {table_name}")
                    table_desc = cursor.fetchall()
                    table_fields = {row[0] for row in table_desc}
                    json_fields = [
                        row[0] for row in table_desc if row[1].lower() in ["longtext", "text", "json", "jsonb"]
                    ]
            except DatabaseError as e:
                Prompt.error(msg="查询表 {table_name} 结构失败, 错误信息: {error}", table_name=table_name, error=str(e))

            query_sql = f"SELECT * FROM {table_name}"

            # 拼接查询条件
            conditions, params = self.get_conditions_and_values_by_query_fields(
                table_fields, query_condition_dict, query_fields
            )

            if conditions:
                query_sql += f" WHERE {' AND '.join(conditions)}"

            data = []
            query_success = True

            try:
                with connection.cursor() as cursor:
                    cursor.execute(query_sql, params)
                    columns = [col[0] for col in cursor.description]
                    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    for row in data:
                        clean_row = {k: v for k, v in row.items() if v is not None}
                        for field in json_fields:
                            if field in clean_row:
                                try:
                                    if clean_row[field]:
                                        clean_row[field] = json.loads(clean_row[field])
                                except (json.JSONDecodeError, TypeError):
                                    pass
                        row.clear()
                        row.update(clean_row)
            except DatabaseError as e:
                Prompt.error(msg="查询表 {table_name} 失败, 错误信息: {error}", table_name=table_name, error=str(e))
                query_success = False

            if query_success:
                if not data:
                    Prompt.error(
                        msg="表 {table_name} 未查询出数据",
                        table_name=table_name,
                    )
                    data = []

                os.makedirs(self.save_path, exist_ok=True)

                filename = f"{table_name}.json"
                file_path = os.path.join(self.save_path, filename)

                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, cls=DateTimeEncoder, ensure_ascii=False)
                except OSError as e:
                    Prompt.error(
                        msg="导出 {table_name} json 文件失败, 错误信息: {error}", table_name=table_name, error=str(e)
                    )

    @staticmethod
    def get_conditions_and_values_by_query_fields(
        table_fields: set, query_condition_dict: dict, query_fields: list = None
    ) -> tuple[list, list]:
        if not query_condition_dict or not table_fields or not query_fields:
            return [], []

        conditions = []
        params = []

        for field in query_fields:
            if field in table_fields and field in query_condition_dict:
                field_query_condition_dict = query_condition_dict.get(field)

                if field_query_condition_dict:
                    conditions.append(field_query_condition_dict.get("condition"))

                    operator = field_query_condition_dict.get("operator", "eq")

                    if operator == "eq":
                        params.append(field_query_condition_dict.get("param"))
                    elif operator == "in":
                        params.extend(field_query_condition_dict.get("param"))

        return conditions, params


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime | date):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super().default(obj)
