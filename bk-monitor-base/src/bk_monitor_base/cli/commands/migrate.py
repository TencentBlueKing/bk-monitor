from typing import Annotated, Any

import typer


def migrate(
    app_label: Annotated[str | None, typer.Argument(help="指定应用标签")] = None,
    migration_name: Annotated[str | None, typer.Argument(help="指定迁移名")] = None,
    database: Annotated[str | None, typer.Option("--database", help="指定数据库")] = None,
    fake: Annotated[bool, typer.Option("--fake", help="标记迁移为已执行但不实际执行")] = False,
    fake_initial: Annotated[bool, typer.Option("--fake-initial", help="检测表已存在时假装已迁移")] = False,
    plan: Annotated[bool, typer.Option("--plan", help="显示将要执行的迁移计划")] = False,
    run_syncdb: Annotated[bool, typer.Option("--run-syncdb", help="为无迁移的应用创建表")] = False,
    check: Annotated[bool, typer.Option("--check", help="有未应用迁移时退出非零状态")] = False,
    prune: Annotated[bool, typer.Option("--prune", help="删除不存在的迁移记录")] = False,
    skip_checks: Annotated[bool, typer.Option("--skip-checks", help="跳过系统检查")] = False,
    noinput: Annotated[bool, typer.Option("--noinput", "--no-input", help="不进行任何交互式提示")] = False,
) -> None:
    """
    执行 Django ORM 迁移命令
    """
    from django.core.management import call_command

    args: list[str] = []
    kwargs: dict[str, Any] = {}

    # 位置参数
    if app_label:
        args.append(app_label)
    if migration_name:
        args.append(migration_name)

    # 选项参数
    if database:
        kwargs["database"] = database
    if fake:
        args.append("--fake")
    if fake_initial:
        args.append("--fake-initial")
    if plan:
        args.append("--plan")
    if run_syncdb:
        args.append("--run-syncdb")
    if check:
        args.append("--check")
    if prune:
        args.append("--prune")
    if skip_checks:
        args.append("--skip-checks")
    if noinput:
        args.append("--no-input")

    call_command("migrate", *args, **kwargs)


def makemigrations(
    app_label: Annotated[list[str] | None, typer.Argument(help="指定应用标签")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="只显示将要生成的迁移文件，不实际写入")] = False,
    merge: Annotated[bool, typer.Option("--merge", help="合并迁移冲突")] = False,
    empty: Annotated[bool, typer.Option("--empty", help="创建空迁移")] = False,
    noinput: Annotated[bool, typer.Option("--noinput", "--no-input", help="不进行任何交互式提示")] = False,
    name: Annotated[str | None, typer.Option("-n", "--name", help="指定迁移文件名")] = None,
    no_header: Annotated[bool, typer.Option("--no-header", help="不添加头部注释")] = False,
    check: Annotated[bool, typer.Option("--check", help="有未生成迁移时退出非零状态")] = False,
    scriptable: Annotated[
        bool, typer.Option("--scriptable", help="日志输出到 stderr，仅将生成的迁移文件路径写到 stdout")
    ] = False,
    update: Annotated[bool, typer.Option("--update", help="合并模型变更到最新迁移并优化操作")] = False,
) -> None:
    """
    生成 Django ORM 迁移文件
    """
    from django.core.management import call_command

    args: list[str] = []
    kwargs: dict[str, Any] = {}
    if app_label:
        args.extend(app_label)

    if dry_run:
        args.append("--dry-run")
    if merge:
        args.append("--merge")
    if empty:
        args.append("--empty")
    if noinput:
        args.append("--no-input")
    if no_header:
        args.append("--no-header")
    if check:
        args.append("--check")
    if scriptable:
        args.append("--scriptable")
    if update:
        args.append("--update")

    if name:
        kwargs["name"] = name

    call_command("makemigrations", *args, **kwargs)
