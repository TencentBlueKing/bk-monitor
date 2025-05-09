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

    ps_cmd = "ps -e -o command"
    result = subprocess.run(ps_cmd, shell=True, check=True, capture_output=True, text=True)
    processes = result.stdout

    # 执行命令
    cmd = f'{cmd_path} --match={match_pattern} --exclude={exclude_pattern} --dimensions="{dimensions_pattern}" --process_name="{process_name_pattern}" --processes="{processes}"'
    result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)
