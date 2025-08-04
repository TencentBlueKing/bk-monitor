import pathlib
import subprocess

if __name__ == "__main__":
    # 获取当前目录
    current_dir = pathlib.Path(__file__).parent

    cmd_path = current_dir / "process_matcher"
    match_pattern = "python"
    exclude_pattern = "worker"
    dimensions_pattern = r"port=(?P<port>\d+)"
    process_name_pattern = r"(python)\d*"

    ps_cmd = ["ps", "-e", "-o", "command"]
    result = subprocess.run(ps_cmd, check=True, capture_output=True, text=True)
    processes = result.stdout

    # 使用列表形式传递命令行参数
    cmd_args = [
        str(cmd_path),
        f"--match={match_pattern}",
        f"--exclude={exclude_pattern}",
        f"--dimensions={dimensions_pattern}",
        f"--process_name={process_name_pattern}",
        f"--processes={processes}",
    ]

    # 使用列表形式执行命令，避免shell注入风险
    result = subprocess.run(cmd_args, check=True, capture_output=True, text=True)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)
