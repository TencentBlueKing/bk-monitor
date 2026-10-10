import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Annotated, Any

import typer


def _project_root() -> Path:
    """
    获取项目根目录（即包含 src/ 的上一级）。

    Notes:
        当前文件路径为：.../src/bk_monitor_base/cli/commands/run_script.py
        因此 project root 为 parents[4]。
    """

    return Path(__file__).resolve().parents[4]


def _resolve_script_path(script_path: str) -> Path:
    """
    解析用户传入的脚本路径。

    支持：
    - 绝对路径
    - 相对路径（优先相对于当前工作目录，其次相对于项目根目录）
    """

    raw = Path(script_path)
    if raw.is_absolute():
        return raw

    cwd_candidate = (Path.cwd() / raw).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    project_candidate = (_project_root() / raw).resolve()
    return project_candidate


def run_script(
    ctx: typer.Context,
    script_path: Annotated[str, typer.Argument(..., help="要执行的 Python 脚本路径（相对或绝对）")],
) -> None:
    """
    执行指定 Python 脚本，并将参数透传给脚本。

    该命令会自动初始化 Django 环境，因此脚本本身不需要显式调用 django_setup。
    """

    # 透传参数：通过 Click 的 allow_extra_args/ignore_unknown_options 收集原始参数
    # 这样脚本侧的 `--xx` 不会被当前命令当作自己的 option 解析。
    args = list(ctx.args)

    resolved_path = _resolve_script_path(script_path)
    if not resolved_path.exists() or not resolved_path.is_file():
        checked_paths: list[str] = []
        raw = Path(script_path)
        if raw.is_absolute():
            checked_paths.append(str(raw))
        else:
            checked_paths.append(str((Path.cwd() / raw).resolve()))
            checked_paths.append(str((_project_root() / raw).resolve()))
        raise typer.BadParameter(
            f"脚本文件不存在或不是文件。\n- 输入: {script_path}\n" + "\n".join([f"- 尝试: {p}" for p in checked_paths]),
            param_hint="script_path",
        )

    # 延迟导入，避免影响 `--help` 等只读场景。
    from bk_monitor_base.django_setup import django_setup

    django_setup()

    old_argv = sys.argv[:]
    old_sys_path = sys.path[:]

    # 将脚本目录加入 sys.path（模拟 `python path/to/script.py ...` 的行为）。
    script_dir = str(resolved_path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    else:
        # 确保脚本目录优先级最高
        sys.path.remove(script_dir)
        sys.path.insert(0, script_dir)

    sys.argv = [str(resolved_path), *args]

    try:
        module_hash = hashlib.sha256(str(resolved_path).encode("utf-8")).hexdigest()[:12]
        module_name = f"bk_monitor_base.cli.run_script_{resolved_path.stem}_{module_hash}"

        spec = importlib.util.spec_from_file_location(module_name, str(resolved_path))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载脚本模块: {resolved_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        main: Any = getattr(module, "main", None)
        if callable(main):
            ret = main()
            # 兼容 `return 0/1` 的写法
            if isinstance(ret, int) and ret != 0:
                raise typer.Exit(code=ret)

    except SystemExit as e:
        # 兼容脚本内部 `sys.exit(code)`/argparse 的退出。
        code = e.code if isinstance(e.code, int) else 1
        raise typer.Exit(code=code) from e
    finally:
        sys.argv = old_argv
        sys.path = old_sys_path
