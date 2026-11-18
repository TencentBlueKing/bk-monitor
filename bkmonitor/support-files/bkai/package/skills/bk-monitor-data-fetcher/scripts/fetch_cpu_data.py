#!/usr/bin/env python3
"""
CPU数据拉取脚本 - fetch_metrics.py的便捷封装

这是一个简化的脚本,专门用于拉取CPU数据。
实际上是调用通用的fetch_metrics.py脚本。

使用方法:
    # 显式指定业务与环境
    python3 fetch_cpu_data.py --biz-id 7 --env stage

    # 自定义业务ID和时间范围
    python3 fetch_cpu_data.py --biz-id 100 --env stage --hours 2

    # 打印详细信息
    python3 fetch_cpu_data.py --biz-id 7 --env stage --verbose

提示:
    如需拉取其他指标(内存、磁盘等),请使用 fetch_metrics.py
"""

import sys
import subprocess
import argparse
import os


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="CPU数据拉取工具 (fetch_metrics.py的便捷封装)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 显式指定业务与环境
  python3 fetch_cpu_data.py --biz-id 7 --env stage

  # 拉取业务100过去2小时的CPU数据
  python3 fetch_cpu_data.py --biz-id 100 --env stage --hours 2

  # 打印详细调试信息
  python3 fetch_cpu_data.py --biz-id 7 --env stage --verbose

提示:
  如需拉取其他指标,请使用:
    python3 fetch_metrics.py --biz-id 7 --env stage --metric memory
    python3 fetch_metrics.py --biz-id 7 --env stage --metric disk
        """,
    )

    parser.add_argument("--biz-id", type=str, required=True, help="用户明确选择的业务ID")

    parser.add_argument("--hours", type=int, default=1, help="时间范围(小时) (默认: 1)")

    parser.add_argument("--verbose", action="store_true", help="打印详细调试信息")

    parser.add_argument("--env", required=True, help="已确认的目标环境标识")
    args = parser.parse_args()

    # 构造fetch_metrics.py的命令
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fetch_metrics_path = os.path.join(script_dir, "fetch_metrics.py")

    cmd = [
        sys.executable,
        fetch_metrics_path,
        "--biz-id",
        args.biz_id,
        "--metric",
        "cpu",
        "--hours",
        str(args.hours),
        "--env",
        args.env,
    ]

    if args.verbose:
        cmd.append("--verbose")

    # 执行命令
    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("❌ 错误: 找不到 fetch_metrics.py")
        print(f"   期望路径: {fetch_metrics_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
