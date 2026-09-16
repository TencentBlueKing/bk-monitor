# 命令行工具

## 概述

项目的命令行工具在 `src/bk_monitor_base/cli` 下定义，使用 [Typer](https://typer.tiangolo.com/) 进行定义。

通过 `uv` 安装项目依赖后，可以直接通过 `bk-monitor-base-cli` 命令运行。

## 安装和配置

```bash
# 安装项目依赖（包含cli分组）
uv sync --all-groups

# 验证安装
bk-monitor-base-cli --help
```

## 可用命令

### 主要命令

```bash
# 显示帮助信息
bk-monitor-base-cli --help

# 显示版本信息
bk-monitor-base-cli --version
```

### Shell命令

```bash
# 启动交互式shell
bk-monitor-base-cli shell
```

### 数据库迁移

```bash
# 生成迁移文件
bk-monitor-base-cli makemigrations

# 运行数据库迁移
bk-monitor-base-cli migrate
```

## 开发新命令

### 基本结构

```python
# src/bk_monitor_base/cli/commands/new_command.py
import typer
from typing import Optional

app = typer.Typer()

@app.command()
def new_command(
    name: str = typer.Argument(..., help="命令名称"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径")
):
    """新命令的描述。"""
    typer.echo(f"执行命令: {name}")
    if verbose:
        typer.echo("详细模式已启用")
    if config:
        typer.echo(f"使用配置文件: {config}")

if __name__ == "__main__":
    app()
```

### 注册命令

```python
# src/bk_monitor_base/cli/app.py
from typer import Typer
from .commands import new_command

app = Typer()
app.add_typer(new_command.app, name="new", help="新命令组")
```
