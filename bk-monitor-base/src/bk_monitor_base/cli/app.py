import typer

from bk_monitor_base.cli.commands import exception_docs, migrate, run_script, shell
from bk_monitor_base.django_setup import django_setup

# 初始化 Django 环境
django_setup()

app = typer.Typer(name="bk-monitor-base", no_args_is_help=True)

# 命令注册
app.command()(migrate.migrate)
app.command()(migrate.makemigrations)
app.command()(shell.shell)
app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})(run_script.run_script)
app.command(name="scan-exceptions")(exception_docs.scan_exception_docs)

if __name__ == "__main__":
    app()
