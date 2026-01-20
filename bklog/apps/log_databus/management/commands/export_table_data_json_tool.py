import json
import os
from datetime import datetime, date

from django.core.management import BaseCommand
from django.db import connection, DatabaseError

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
        parser.add_argument(
            "--table_names",
            help="需要导出的表名, 例如: log_search_logindexset,log_search_logindexsetdata",
            required=True,
        )

    def handle(self, *args, **options):
        ExportTableDataJsonTool(
            save_path=options["path"],
            table_names_str=options["table_names"],
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
        self.index_set_ids_set = set(parse_str_int_list(index_set_ids_str))

    def batch_export(self):
        """
        批量导出
        """
        where_condition_dict = {}

        if self.bk_biz_id:
            where_condition_dict["bk_biz_id"] = {"condition": "bk_biz_id = %s", "param": self.bk_biz_id}

        if self.index_set_ids_set:
            placeholders = ", ".join(["%s"] * len(self.index_set_ids_set))
            where_condition_dict["index_set_id"] = {
                "condition": f"index_set_id IN ({placeholders})",
                "param": list(self.index_set_ids_set),
            }

        for table_name in self.table_names_set:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"DESCRIBE {table_name}")
                    table_fields = {row[0] for row in cursor.fetchall()}
            except DatabaseError as e:
                Prompt.error(msg="查询表 {table_name} 结构失败, 错误信息: {error}", table_name=table_name, error=str(e))
                table_fields = set()

            query_sql = f"SELECT * FROM {table_name}"

            # 拼接查询条件
            where_conditions = []
            params = []
            if where_condition_dict:
                if "bk_biz_id" in table_fields and "bk_biz_id" in where_condition_dict:
                    where_conditions.append(where_condition_dict.get("bk_biz_id").get("condition"))
                    params.append(where_condition_dict.get("bk_biz_id").get("param"))
                if "index_set_id" in table_fields and "index_set_id" in where_condition_dict:
                    where_conditions.append(where_condition_dict.get("index_set_id").get("condition"))
                    params.extend(where_condition_dict.get("index_set_id").get("param"))

            if where_conditions:
                query_sql += f" WHERE {' AND '.join(where_conditions)}"

            data = []
            query_success = True

            try:
                with connection.cursor() as cursor:
                    cursor.execute(query_sql, params)
                    columns = [col[0] for col in cursor.description]
                    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
            except DatabaseError as e:
                Prompt.error(msg="查询表 {table_name} 失败, 错误信息: {error}", table_name=table_name, error=str(e))
                query_success = False

            if query_success:
                if not data:
                    Prompt.error(
                        msg="表 {table_name} 未查询出数据",
                        table_name=table_name,
                    )
                    continue

                os.makedirs(self.save_path, exist_ok=True)

                filename = f"{table_name}.json"
                file_path = os.path.join(self.save_path, filename)

                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
                except OSError as e:
                    Prompt.error(
                        msg="导出 {table_name} json 文件失败, 错误信息: {error}", table_name=table_name, error=str(e)
                    )


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime | date):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super().default(obj)
