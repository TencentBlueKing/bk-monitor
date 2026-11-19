#!/usr/bin/env python3
"""
通用指标数据拉取脚本

支持:
  - 预定义指标 (cpu/memory/disk/load/net_recv/net_sent)
  - 任意 PromQL 查询
  - --env 显式指定目标环境
  - 自动 server 名称解析 (新旧格式兼容)
  - --start-time / --end-time 直接指定时间戳

使用方法:
    python3 fetch_metrics.py --biz-id 7 --env stage --metric cpu --hours 1
    python3 fetch_metrics.py --biz-id 7 --hours 1 --env stage \\
        --promql "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))" \\
        --output cpu_metrics
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

PREDEFINED_METRICS = {
    "cpu": {
        "name": "CPU使用率",
        "promql": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
        "unit": "%",
    },
    "memory": {
        "name": "内存使用率",
        "promql": "avg(avg_over_time(bkmonitor:system:mem:pct_used[1m]))",
        "unit": "%",
    },
    "disk": {
        "name": "磁盘使用率",
        "promql": "avg(avg_over_time(bkmonitor:system:disk:in_use[1m]))",
        "unit": "%",
    },
    "load": {
        "name": "系统负载",
        "promql": "avg(avg_over_time(bkmonitor:system:load:load5[1m]))",
        "unit": "",
    },
    "net_recv": {
        "name": "网卡入流量",
        "promql": "avg(avg_over_time(bkmonitor:system:net:speed_recv[1m]))",
        "unit": "KB/s",
    },
    "net_sent": {
        "name": "网卡出流量",
        "promql": "avg(avg_over_time(bkmonitor:system:net:speed_sent[1m]))",
        "unit": "KB/s",
    },
}


def fetch_metrics(
    client: MCPClient, biz_id: str, promql: str, start_time: int, end_time: int, step: str = "1m", env: str = None
):
    """拉取指标数据, 返回 MCP 原始结果。"""
    validate_query_window(start_time, end_time)
    server_name = client.find_server(env, "metrics-query")
    result = client.call_tool(
        server_name,
        "execute_range_query",
        {
            "body_param": {
                "bk_biz_id": str(biz_id),
                "promql": promql,
                "start_time": str(start_time),
                "end_time": str(end_time),
                "step": step,
            }
        },
        retries=1,
    )
    raise_if_business_error(result, context=f"{server_name}/execute_range_query")
    return result


def print_statistics(result: dict, metric_name: str = "指标", unit: str = ""):
    """打印数据统计信息。"""
    print("\n" + "=" * 60)
    print("数据拉取成功!")
    print("=" * 60)

    try:
        parsed = parse_mcp_result(result)
        body = parsed.get("response_body", parsed) if isinstance(parsed, dict) else parsed
        series_data = []
        if isinstance(body, dict):
            series_data = body.get("data", {}).get("series", [])

        if not series_data:
            print("未找到 series 数据")
            return

        print(f"返回序列数: {len(series_data)}")

        for i, series in enumerate(series_data):
            datapoints = series.get("datapoints", [])
            alias = series.get("alias", "未命名")

            print(f"\n序列 {i + 1} ({alias}):")
            print(f"  数据点数: {len(datapoints)}")

            if not datapoints:
                continue

            first = datapoints[0]
            last = datapoints[-1]

            first_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(first[1] / 1000))
            last_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last[1] / 1000))

            print(f"  首个数据点: {first_time}, {metric_name}={first[0]:.2f}{unit}")
            print(f"  最后数据点: {last_time}, {metric_name}={last[0]:.2f}{unit}")

            values = [dp[0] for dp in datapoints if dp[0] is not None]
            if values:
                avg_val = sum(values) / len(values)
                print(f"  平均{metric_name}: {avg_val:.2f}{unit}")
                print(f"  最大{metric_name}: {max(values):.2f}{unit}")
                print(f"  最小{metric_name}: {min(values):.2f}{unit}")

                if len(values) > 1 and values[0] != 0:
                    trend = (values[-1] - values[0]) / values[0] * 100
                    symbol = "↑" if trend > 0 else "↓" if trend < 0 else "→"
                    print(f"  变化趋势: {symbol} {abs(trend):.2f}%")

    except Exception as e:
        print(f"解析数据统计时出错: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="通用指标数据拉取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
预定义指标: {", ".join(PREDEFINED_METRICS.keys())}

示例:
  python3 fetch_metrics.py --biz-id 7 --env stage --metric cpu --hours 1
  python3 fetch_metrics.py --biz-id 7 --metric cpu --hours 1 --env stage
  python3 fetch_metrics.py --biz-id 7 --env stage --hours 2 \\
      --promql "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))" \\
      --output cpu_metrics
        """,
    )

    parser.add_argument("--biz-id", type=str, required=True, help="业务ID")
    parser.add_argument("--env", type=str, required=True, help="已确认的目标环境标识")
    parser.add_argument("--metric", type=str, choices=list(PREDEFINED_METRICS.keys()), help="预定义指标")
    parser.add_argument("--promql", type=str, help="自定义PromQL (与--metric二选一)")
    parser.add_argument("--hours", type=int, default=1, help="时间范围/小时 (默认: 1)")
    parser.add_argument("--start-time", type=int, help="开始时间戳/秒")
    parser.add_argument("--end-time", type=int, help="结束时间戳/秒")
    parser.add_argument("--step", type=str, default="1m", help="查询步长 (默认: 1m)")
    parser.add_argument("--output", type=str, help="输出文件路径 (如 bkmonitor-files/cpu.json)")
    parser.add_argument("--verbose", action="store_true", help="详细调试信息")

    args = parser.parse_args()

    if not args.metric and not args.promql:
        parser.error("必须指定 --metric 或 --promql 之一")
    if args.metric and args.promql:
        parser.error("--metric 和 --promql 不能同时使用")

    if args.metric:
        info = PREDEFINED_METRICS[args.metric]
        promql = info["promql"]
        metric_name = info["name"]
        unit = info["unit"]
    else:
        promql = args.promql
        metric_name = "值"
        unit = ""

    end_time = args.end_time if args.end_time is not None else int(time.time())
    start_time = args.start_time if args.start_time is not None else end_time - args.hours * 3600
    try:
        validate_query_window(start_time, end_time)
    except ValueError as error:
        parser.error(str(error))

    print("=" * 60)
    print(f"拉取业务{args.biz_id}的{metric_name}数据 (env={args.env})")
    print("=" * 60)
    print("\n时间范围:")
    print(f"  开始: {start_time} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))})")
    print(f"  结束: {end_time} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))})")
    print(f"  跨度: {(end_time - start_time) / 3600:.1f} 小时")
    print(f"\n查询: {promql}")
    print(f"步长: {args.step}")

    try:
        client = MCPClient(verbose=args.verbose)
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)

    try:
        result = fetch_metrics(
            client,
            args.biz_id,
            promql,
            start_time,
            end_time,
            step=args.step,
            env=args.env,
        )
    except Exception as e:
        print(f"\n❌ 查询失败: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        tag = args.metric or "metrics"
        output_path = f"bkmonitor-files/{tag}_biz{args.biz_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"

    parsed = parse_mcp_result(result)
    body = parsed.get("response_body", parsed) if isinstance(parsed, dict) else parsed
    output_result(body, output_path)

    print_statistics(result, metric_name, unit)
    print(f"\n文件路径: {output_path}")


if __name__ == "__main__":
    main()
