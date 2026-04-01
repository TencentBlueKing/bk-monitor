"""
通过 UnifyQuery 查询日志数据并导出 _id 列表，支持跨环境对比

导出文件格式为 JSON，包含查询元信息和排序后的 _id 列表，
在另一个环境对比时只需传入该文件，脚本会自动读取参数并查询对比。

使用说明:
    本脚本用于跨环境对比日志数据的一致性（基于 _id 字段），分为「导出」和「对比」两个步骤：
      1. 在环境A执行导出，生成包含查询元信息和 _id 列表的 JSON 文件
      2. 将该文件拷贝到环境B，执行对比命令，脚本自动读取文件中的参数查询本地并输出差异

参数说明:
    --index_set_id  索引集ID（导出模式必填）
    --start_time    开始时间，格式 'YYYY-MM-DD HH:MM:SS'，不传默认15分钟前
    --end_time      结束时间，格式 'YYYY-MM-DD HH:MM:SS'，不传默认当前时间
    --size          查询条数，默认100
    --compare_file  对比模式：传入导出文件路径，自动查询本地并对比

用法示例:
    ==================== 导出模式 ====================

    # 最简用法：仅指定索引集，时间默认最近15分钟，条数默认100
    python manage.py compare_log_ids --index_set_id=1

    # 指定时间范围和条数
    python manage.py compare_log_ids --index_set_id=1 \
        --start_time="2024-01-01 00:00:00" --end_time="2024-01-02 00:00:00" \
        --size=500

    ==================== 对比模式 ====================

    # 将环境A的导出文件拷贝到环境B后，一条命令完成对比
    python manage.py compare_log_ids --compare_file=/tmp/env_a_export.json
"""

import json
import os
from datetime import datetime, timedelta

from django.core.management import BaseCommand

from apps.log_search.models import LogIndexSet
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from bkm_space.utils import space_uid_to_bk_biz_id


class Command(BaseCommand):
    help = "通过 UnifyQuery 查询日志并导出 _id 列表，支持跨环境一键对比"

    def add_arguments(self, parser):
        # ===== 导出模式参数 =====
        parser.add_argument(
            "--index_set_id",
            type=int,
            default=None,
            help="索引集ID（导出模式必填）",
        )
        parser.add_argument(
            "--start_time",
            type=str,
            default=None,
            help="开始时间，格式: 'YYYY-MM-DD HH:MM:SS'（不传默认最近15分钟）",
        )
        parser.add_argument(
            "--end_time",
            type=str,
            default=None,
            help="结束时间，格式: 'YYYY-MM-DD HH:MM:SS'（不传默认当前时间）",
        )
        parser.add_argument(
            "--size",
            type=int,
            default=100,
            help="查询条数，默认100",
        )
        # ===== 对比模式参数 =====
        parser.add_argument(
            "--compare_file",
            type=str,
            default=None,
            help="对比模式: 传入另一个环境的导出文件路径，自动读取参数查询本地并对比",
        )

    def handle(self, *args, **options):
        if options["compare_file"]:
            self._handle_compare(options)
        else:
            self._handle_export(options)

    # ==================== 导出模式 ====================

    def _handle_export(self, options):
        """导出模式：查询日志并导出 _id 列表到文件"""
        index_set_id = options["index_set_id"]
        start_time = options["start_time"]
        end_time = options["end_time"]
        size = options["size"]

        # 参数校验
        if not index_set_id:
            self.stderr.write(self.style.ERROR("错误: 导出模式必须指定 --index_set_id"))
            return

        # 未传时间参数时，默认最近15分钟
        if not start_time or not end_time:
            now = datetime.now()
            end_time = end_time or now.strftime("%Y-%m-%d %H:%M:%S")
            start_time = start_time or (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            self.stdout.write(f"未指定时间范围，默认使用最近15分钟: {start_time} ~ {end_time}")

        # 查询
        id_list, total = self._query_ids(index_set_id, start_time, end_time, size)
        if id_list is None:
            return  # 查询失败，错误信息已在 _query_ids 中输出

        # 构建导出数据（包含元信息）
        export_data = {
            "meta": {
                "index_set_id": index_set_id,
                "start_time": start_time,
                "end_time": end_time,
                "size": size,
                "total": total,
                "export_count": len(id_list),
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "ids": sorted(id_list),
        }

        # 生成输出文件路径: export_<index_set_id>_<start>_<end>.json
        safe_start = start_time.replace(" ", "-").replace(":", "")
        safe_end = end_time.replace(" ", "-").replace(":", "")
        output_path = f"export_{index_set_id}_{safe_start}_{safe_end}.json"

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        abs_path = os.path.abspath(output_path)
        self.stdout.write(self.style.SUCCESS("\n导出成功!"))
        self.stdout.write(f"  文件: {abs_path}")
        self.stdout.write(f"  匹配总数: {total}, 导出ID数: {len(id_list)}")
        self.stdout.write("\n将此文件拷贝到另一个环境后，执行以下命令即可对比:")
        self.stdout.write(f"  python manage.py compare_log_ids --compare_file={abs_path}")

    # ==================== 对比模式 ====================

    def _handle_compare(self, options):
        """对比模式：读取导出文件中的参数，查询本地环境并对比"""
        compare_file = options["compare_file"]

        if not os.path.exists(compare_file):
            self.stderr.write(self.style.ERROR(f"错误: 文件不存在: {compare_file}"))
            return

        # 1. 读取导出文件
        try:
            with open(compare_file, encoding="utf-8") as f:
                remote_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.stderr.write(self.style.ERROR(f"错误: 无法解析导出文件: {e}"))
            return

        # 校验文件格式
        if "meta" not in remote_data or "ids" not in remote_data:
            self.stderr.write(self.style.ERROR("错误: 文件格式不正确，缺少 meta 或 ids 字段"))
            return

        meta = remote_data["meta"]
        remote_ids = remote_data["ids"]
        index_set_id = meta["index_set_id"]
        start_time = meta["start_time"]
        end_time = meta["end_time"]
        size = meta["size"]

        self.stdout.write(f"{'=' * 60}")
        self.stdout.write("导出文件信息:")
        self.stdout.write(f"  索引集ID: {index_set_id}")
        self.stdout.write(f"  时间范围: {start_time} ~ {end_time}")
        self.stdout.write(f"  查询条数: {size}")
        self.stdout.write(f"  导出ID数: {len(remote_ids)}")
        self.stdout.write(f"  导出时间: {meta.get('exported_at', '未知')}")
        self.stdout.write(f"{'=' * 60}")

        # 2. 用相同参数查询本地环境
        self.stdout.write("\n正在用相同参数查询本地环境...")
        local_ids, local_total = self._query_ids(index_set_id, start_time, end_time, size)
        if local_ids is None:
            return

        local_ids = sorted(local_ids)

        # 3. 对比
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write("对比结果:")
        self.stdout.write(f"{'=' * 60}")

        set_remote = set(remote_ids)
        set_local = set(local_ids)

        common = set_remote & set_local
        only_in_remote = set_remote - set_local
        only_in_local = set_local - set_remote

        self.stdout.write(f"  导出文件(远程) ID数: {len(remote_ids)}")
        self.stdout.write(f"  本地查询 ID数:       {len(local_ids)}")
        self.stdout.write(f"  共同存在:            {len(common)}")
        self.stdout.write(f"  仅在远程:            {len(only_in_remote)}")
        self.stdout.write(f"  仅在本地:            {len(only_in_local)}")

        if len(set_remote) > 0:
            match_rate = len(common) / len(set_remote) * 100
            self.stdout.write(f"  匹配率:              {match_rate:.2f}%")

        if not only_in_remote and not only_in_local:
            self.stdout.write(self.style.SUCCESS("\n✅ 两个环境的日志 _id 完全一致!"))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️  两个环境的日志 _id 存在差异!"))

    # ==================== 公共方法 ====================

    def _query_ids(self, index_set_id, start_time, end_time, size):
        """
        查询指定索引集的日志并提取 _id 列表

        :return: (id_list, total) 或 (None, None) 表示失败
        """
        # 1. 校验索引集
        index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if not index_set_obj:
            self.stderr.write(self.style.ERROR(f"错误: 索引集 {index_set_id} 不存在"))
            return None, None

        # 2. 获取业务ID
        bk_biz_id = space_uid_to_bk_biz_id(index_set_obj.space_uid)
        if not bk_biz_id:
            self.stderr.write(self.style.ERROR(f"错误: 无法从 space_uid={index_set_obj.space_uid} 获取 bk_biz_id"))
            return None, None

        self.stdout.write(
            f"索引集: {index_set_obj.index_set_name} (ID={index_set_id})\n"
            f"业务ID: {bk_biz_id}\n"
            f"时间范围: {start_time} ~ {end_time}\n"
            f"查询条数: {size}"
        )

        # 3. 构建查询参数
        search_params = {
            "index_set_ids": [index_set_id],
            "bk_biz_id": bk_biz_id,
            "keyword": "*",
            "start_time": start_time,
            "end_time": end_time,
            "begin": 0,
            "size": size,
            "can_highlight": False,
        }

        # 4. 执行查询
        self.stdout.write("正在查询...")
        try:
            handler = UnifyQueryHandler(search_params)
            result = handler.search(search_type=None)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"查询失败: {e}"))
            return None, None

        log_list = result.get("list", []) or []
        total = result.get("total", 0)

        self.stdout.write(f"查询完成: 匹配总数={total}, 本次获取={len(log_list)} 条")

        if not log_list:
            self.stdout.write(self.style.WARNING("未查询到数据"))
            return [], total

        # 5. 提取 _id
        id_list = self._extract_ids(log_list)
        self.stdout.write(f"成功提取 {len(id_list)} 个文档ID")

        return id_list, total

    @staticmethod
    def _extract_ids(log_list):
        """从日志列表中提取文档 _id"""
        id_list = []
        for log_item in log_list:
            # UnifyQuery 返回的 list 中，__doc_id 被转换为 __id__
            doc_id = log_item.get("__id__") or log_item.get("__doc_id") or log_item.get("_id")
            if doc_id:
                id_list.append(str(doc_id))

        return id_list
