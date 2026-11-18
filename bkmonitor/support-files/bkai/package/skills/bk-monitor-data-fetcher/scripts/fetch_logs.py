#!/usr/bin/env python3
"""
通用日志拉取脚本

支持:
  - 按索引集名称模糊搜索 / 按索引集 ID 精确查询
  - 按时间片分批取数 (可能截断或重复，不能保证全量)
  - 自定义 Lucene 查询条件
  - --env 显式指定目标环境
  - 自动 server 名称解析 (新旧格式兼容)

使用方法:
    python3 fetch_logs.py --biz-id 2 --env stage --index-name backend --hours 1
    python3 fetch_logs.py --biz-id 2 --env stage --index-name backend --hours 1 --fetch-all
    python3 fetch_logs.py --biz-id 2 --env stage --index-name backend --hours 1 \\
        --query "level:ERROR" --fetch-all
    python3 fetch_logs.py --biz-id 2 --env stage --index-set-id 322 --hours 1
    python3 fetch_logs.py --biz-id 2 --env stage --list-indexes
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_data_fetcher import (
    MCPClient,
    output_result,
    parse_mcp_result,
    raise_if_business_error,
    validate_query_window,
)


def find_index_set(client: MCPClient, biz_id: str, env: str, index_name: str = None, index_set_id: str = None):
    """查找索引集, 支持模糊匹配和精确 ID。"""
    if index_set_id:
        return {"index_set_id": index_set_id, "index_set_name": f"索引集{index_set_id}"}

    print(f"正在查找索引集: {index_name}...")
    server_name = client.find_server(env, "log-query")

    try:
        result = client.call_tool(
            server_name,
            "list_index_sets",
            {"query_param": {"bk_biz_id": str(biz_id)}},
            retries=1,
        )
        raise_if_business_error(result, context=f"{server_name}/list_index_sets")

        parsed = parse_mcp_result(result)
        body = parsed.get("response_body", parsed) if isinstance(parsed, dict) else parsed
        index_sets = body.get("data", []) if isinstance(body, dict) else []

        print(f"找到 {len(index_sets)} 个索引集")

        matches = []
        for idx in index_sets:
            idx_name = idx.get("index_set_name", "")
            idx_id = idx.get("index_set_id")
            if index_name.lower() in idx_name.lower():
                matches.append(idx)
                print(f"  ✓ 匹配: [{idx_id}] {idx_name}")

        if not matches:
            print(f"\n❌ 未找到包含 '{index_name}' 的索引集")
            print("提示: 使用 --list-indexes 查看所有可用索引集")
            return None

        if len(matches) > 1:
            print(f"\n❌ 找到 {len(matches)} 个匹配，请确认后使用 --index-set-id")
            return None

        return matches[0]

    except Exception as e:
        print(f"❌ 查找索引集失败: {e}")
        return None


def fetch_logs_batch(
    client: MCPClient,
    biz_id: str,
    index_set_id: str,
    start_time: int,
    end_time: int,
    env: str,
    query_string: str = "*",
    limit: int = 500,
):
    """拉取一批日志, 返回 (logs, total)。"""
    validate_query_window(start_time, end_time)
    if limit <= 0:
        raise ValueError("limit 必须大于 0")
    server_name = client.find_server(env, "log-query")

    try:
        result = client.call_tool(
            server_name,
            "search_logs",
            {
                "body_param": {
                    "bk_biz_id": str(biz_id),
                    "index_set_id": str(index_set_id),
                    "query_string": query_string,
                    "start_time": str(start_time),
                    "end_time": str(end_time),
                    "limit": str(limit),
                }
            },
            retries=1,
        )
        raise_if_business_error(result, context=f"{server_name}/search_logs")

        parsed = parse_mcp_result(result)
        body = parsed.get("response_body", parsed) if isinstance(parsed, dict) else parsed
        data = body.get("data", {}) if isinstance(body, dict) else {}

        total = data.get("total", 0)
        logs = data.get("list", [])
        return logs, total

    except Exception as e:
        raise RuntimeError(f"拉取日志失败: {e}") from e


def fetch_all_logs(
    client: MCPClient,
    biz_id: str,
    index_set_id: str,
    start_time: int,
    end_time: int,
    env: str,
    query_string: str = "*",
    batch_size: int = 500,
    max_batches: int = 20,
):
    """按时间片取数；受批次数与每片上限约束，不保证全量或无重复。"""
    validate_query_window(start_time, end_time)
    if batch_size <= 0 or max_batches <= 0:
        raise ValueError("batch_size 和 max_batches 必须大于 0")
    print("\n开始分批拉取日志...")
    print(f"  批次大小: {batch_size}")
    print(f"  最大批次: {max_batches}")

    _, total = fetch_logs_batch(
        client,
        biz_id,
        index_set_id,
        start_time,
        end_time,
        env,
        query_string,
        limit=1,
    )

    if total == 0:
        print("❌ 未获取到任何日志")
        return []

    print(f"  总日志数: {total}")

    needed_batches = min((total + batch_size - 1) // batch_size, max_batches, end_time - start_time)
    if total > needed_batches * batch_size:
        print(f"⚠️  日志总数 {total} 超过上限 ({needed_batches}批×{batch_size}条)")

    total_duration = end_time - start_time
    segment = total_duration / needed_batches

    all_logs = []
    for i in range(needed_batches):
        seg_start = int(start_time + i * segment)
        seg_end = end_time if i == needed_batches - 1 else int(start_time + (i + 1) * segment)

        print(
            f"\n批次 {i + 1}/{needed_batches}: "
            f"{time.strftime('%H:%M:%S', time.localtime(seg_start))} - "
            f"{time.strftime('%H:%M:%S', time.localtime(seg_end))}"
        )

        logs, segment_total = fetch_logs_batch(
            client,
            biz_id,
            index_set_id,
            seg_start,
            seg_end,
            env,
            query_string,
            batch_size,
        )

        if logs:
            all_logs.extend(logs)
            print(f"  获取 {len(logs)} 条日志 (累计: {len(all_logs)} 条)")
        else:
            print("  该时间段无日志")
        if segment_total > len(logs):
            print(f"  ⚠️ 此时间片报告 {segment_total} 条，仅返回 {len(logs)} 条，结果已截断")

        if i < needed_batches - 1:
            time.sleep(0.5)

    print(f"\n分批请求结束，共返回 {len(all_logs)} 条；可能截断或重复，不能据此确认全量覆盖")
    return all_logs


def main():
    parser = argparse.ArgumentParser(
        description="通用日志拉取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 fetch_logs.py --biz-id 2 --env stage --index-name backend --hours 1
  python3 fetch_logs.py --biz-id 2 --env stage --index-name backend --hours 1 --fetch-all
  python3 fetch_logs.py --biz-id 2 --env stage --index-name backend --hours 1 \\
      --query "level:ERROR" --fetch-all
  python3 fetch_logs.py --biz-id 2 --env stage --index-set-id 322 --hours 1
  python3 fetch_logs.py --biz-id 2 --env stage --list-indexes
        """,
    )

    parser.add_argument("--biz-id", type=str, required=True, help="业务ID")
    parser.add_argument("--env", type=str, required=True, help="已确认的目标环境标识")
    parser.add_argument("--index-name", type=str, help="索引集名称 (模糊匹配)")
    parser.add_argument("--index-id", type=str, dest="index_id", help="索引集ID (精确匹配)")
    parser.add_argument("--index-set-id", type=str, dest="index_set_id", help="索引集ID (精确匹配, 与 --index-id 等价)")
    parser.add_argument("--hours", type=int, default=1, help="时间范围/小时 (默认: 1)")
    parser.add_argument("--start-time", type=int, help="开始时间戳/秒")
    parser.add_argument("--end-time", type=int, help="结束时间戳/秒")
    parser.add_argument("--query", type=str, default="*", help="Lucene 查询条件 (默认: *)")
    parser.add_argument("--limit", type=int, default=500, help="单批数量 (默认: 500)")
    parser.add_argument("--fetch-all", action="store_true", help="按时间片分批取数，可能截断或重复")
    parser.add_argument("--max-batches", type=int, default=20, help="最大批次数 (默认: 20)")
    parser.add_argument("--list-indexes", action="store_true", help="列出所有索引集")
    parser.add_argument("--output", type=str, help="输出文件路径 (如 bkmonitor-files/logs.json)")
    parser.add_argument("--verbose", action="store_true", help="详细调试信息")

    args = parser.parse_args()

    # --index-set-id 与 --index-id 合并
    effective_index_id = args.index_set_id or args.index_id
    if not args.list_indexes:
        end_time = args.end_time if args.end_time is not None else int(time.time())
        start_time = args.start_time if args.start_time is not None else end_time - args.hours * 3600
        try:
            validate_query_window(start_time, end_time)
        except ValueError as error:
            parser.error(str(error))
        if args.limit <= 0 or args.max_batches <= 0:
            parser.error("--limit 和 --max-batches 必须大于 0")

    try:
        client = MCPClient(verbose=args.verbose)
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)

    # 列出索引集
    if args.list_indexes:
        server_name = client.find_server(args.env, "log-query")
        try:
            result = client.call_tool(
                server_name,
                "list_index_sets",
                {"query_param": {"bk_biz_id": args.biz_id}},
                retries=1,
            )
            raise_if_business_error(result, context=f"{server_name}/list_index_sets")

            parsed = parse_mcp_result(result)
            body = parsed.get("response_body", parsed) if isinstance(parsed, dict) else parsed
            index_sets = body.get("data", []) if isinstance(body, dict) else []

            print(f"\n业务 {args.biz_id} 的索引集列表 (env={args.env}):")
            print("=" * 60)
            for idx in index_sets[:50]:
                print(f"[{idx.get('index_set_id')}] {idx.get('index_set_name')}")
            if len(index_sets) > 50:
                print(f"\n... 还有 {len(index_sets) - 50} 个索引集未显示")

        except Exception as e:
            print(f"❌ 获取索引集列表失败: {e}")
            sys.exit(1)
        sys.exit(0)

    if not args.index_name and not effective_index_id:
        parser.error("必须指定 --index-name 或 --index-set-id")

    print("=" * 60)
    print(f"拉取业务{args.biz_id}的日志 (env={args.env})")
    print("=" * 60)

    index_set = find_index_set(client, args.biz_id, args.env, args.index_name, effective_index_id)
    if not index_set:
        sys.exit(1)

    index_set_id = index_set.get("index_set_id")
    index_set_name = index_set.get("index_set_name", "unknown")

    print("\n配置:")
    print(f"  索引集: [{index_set_id}] {index_set_name}")
    print(f"  查询: {args.query}")
    print(
        f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))} ~ "
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}"
    )

    if args.fetch_all:
        all_logs = fetch_all_logs(
            client,
            args.biz_id,
            index_set_id,
            start_time,
            end_time,
            args.env,
            args.query,
            args.limit,
            args.max_batches,
        )
        if not all_logs:
            sys.exit(1)
        save_data = {"returned_count": len(all_logs), "coverage_guaranteed": False, "list": all_logs}
    else:
        print("\n开始拉取日志...")
        logs, total = fetch_logs_batch(
            client,
            args.biz_id,
            index_set_id,
            start_time,
            end_time,
            args.env,
            args.query,
            args.limit,
        )
        if not logs:
            print("❌ 未获取到任何日志")
            sys.exit(1)
        print(f"✓ 获取 {len(logs)} 条日志 (总计: {total} 条)")
        save_data = {"total": total, "list": logs}
        save_data["truncated"] = total > len(logs)

    save_data["start_time"] = str(start_time)
    save_data["end_time"] = str(end_time)

    if args.output:
        output_path = args.output
    else:
        safe_name = index_set_name.replace("[", "").replace("]", "").replace(" ", "_")
        suffix = "all" if args.fetch_all else str(args.limit)
        output_path = f"bkmonitor-files/logs_{safe_name}_{args.hours}h_{suffix}_{time.strftime('%Y%m%d_%H%M%S')}.json"

    output_result(save_data, output_path)

    logs_list = save_data.get("list", [])
    if logs_list:
        print("\n前3条日志预览:")
        for i, log in enumerate(logs_list[:3]):
            print(f"\n  日志 {i + 1}:")
            if "dtEventTimeStamp" in log:
                ts = int(log["dtEventTimeStamp"])
                if ts > 10_000_000_000:
                    ts = ts // 1000
                print(f"    时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}")
            if "log" in log:
                print(f"    内容: {str(log['log'])[:150]}...")

    print(f"\n文件路径: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"❌ 查询未完成: {error}", file=sys.stderr)
        sys.exit(1)
