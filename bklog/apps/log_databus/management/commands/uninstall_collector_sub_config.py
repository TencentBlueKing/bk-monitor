"""
卸载子配置工具：停用指定业务下所有采集项（卸载节点管理/容器子配置），自定义上报不处理。

逻辑等价于界面上对每个采集项点击「停用」：
  - 主机采集项：节点管理订阅 disable + 下发 STOP 任务（卸载主机上的采集子配置）
  - 容器采集项：删除容器采集 release（卸载容器子配置）
  - 同时置 is_active=False、停用索引集（可选）、停用结果表

「自定义上报」不处理：即排除 collector_scenario_id in [custom, client]
（与采集项列表 NOT_CUSTOM 过滤口径一致）。
"""
import sys

from django.core.management import BaseCommand, CommandError

from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import CollectorScenarioEnum
from apps.utils.local import activate_request
from apps.utils.thread import generate_request

# 自定义上报对应的采集场景，停用时跳过
CUSTOM_REPORT_SCENARIO_IDS = [
    CollectorScenarioEnum.CUSTOM.value,
    CollectorScenarioEnum.CLIENT.value,
]


def parse_bk_biz_id_list(value: str | int | None) -> list[int]:
    """与 overseas_migrate_tool 一致：支持 20 或 20,21,22。此处不允许为空/0。"""
    if value is None:
        return []
    if isinstance(value, int):
        return [] if value == 0 else [value]
    s = str(value).strip()
    if not s or s == "0":
        return []
    try:
        return [int(x.strip()) for x in s.split(",") if x.strip()]
    except ValueError as e:
        raise CommandError(f"无效的 bk_biz_id 列表: {value!r}，请使用整数或逗号分隔，如 1,2,3") from e


def parse_str_int_list(str_list: str) -> list[int]:
    """解析字符串为 int 列表"""
    if not str_list:
        return []
    try:
        return [int(i.strip()) for i in str_list.split(",") if i.strip()]
    except ValueError as e:
        raise CommandError(f"解析失败: {str_list!r}, 请输入逗号分隔的数字") from e


def str_to_bool(value):
    """将字符串转换为布尔值，支持多种常见写法"""
    if isinstance(value, bool):
        return value
    lower_value = value.lower().strip()
    if lower_value in ("true", "1", "yes", "y"):
        return True
    elif lower_value in ("false", "0", "no", "n"):
        return False
    else:
        raise CommandError(f"无效的布尔值: {value}, 请使用 True/False、1/0、yes/no、y/n")


class Command(BaseCommand):
    """停用指定业务下所有采集项（卸载子配置）指令类"""

    def add_arguments(self, parser):
        parser.add_argument(
            "-b",
            "--bk_biz_id",
            help="需要停用采集项的业务 ID，逗号分隔多个，如 1,2,3（必填，禁止为空/0）",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--collector_config_ids",
            help="进一步限定到指定采集项 ID，逗号分隔，如 100,101；不传则停用业务下全部采集项",
            type=str,
            default="",
        )
        parser.add_argument(
            "--is_stop_index_set",
            help="是否同时停用索引集，例如: True/False、1/0、yes/no、y/n，默认 True",
            type=str_to_bool,
            default=True,
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            help="仅打印将被停用的采集项，不实际执行",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--yes",
            help="跳过二次确认，直接执行",
            action="store_true",
            default=False,
        )

    def handle(self, *args, **options):
        bk_biz_ids = parse_bk_biz_id_list(options["bk_biz_id"])
        if not bk_biz_ids:
            raise CommandError("参数 -b/--bk_biz_id 必填且不能为空/0，请明确指定业务 ID")

        collector_config_ids = parse_str_int_list(options["collector_config_ids"])
        is_stop_index_set = options["is_stop_index_set"]
        dry_run = options["dry_run"]
        skip_confirm = options["yes"]

        # 筛选：指定业务下、当前启用、且非「自定义上报」的采集项
        queryset = (
            CollectorConfig.objects.filter(bk_biz_id__in=bk_biz_ids, is_active=True)
            .exclude(collector_scenario_id__in=CUSTOM_REPORT_SCENARIO_IDS)
            .order_by("bk_biz_id", "collector_config_id")
        )
        if collector_config_ids:
            queryset = queryset.filter(collector_config_id__in=collector_config_ids)

        collectors = list(queryset)

        if not collectors:
            Prompt.warning(
                msg="未找到匹配的待停用采集项（业务={biz}，已排除自定义上报、已停用项）",
                biz=",".join(map(str, bk_biz_ids)),
            )
            return

        Prompt.info(
            msg="共筛选出 {count} 个待停用采集项（业务={biz}，is_stop_index_set={iss}）：",
            count=len(collectors),
            biz=",".join(map(str, bk_biz_ids)),
            iss=is_stop_index_set,
        )
        for c in collectors:
            Prompt.print(
                "  - [biz {bk_biz_id}] id={cid} scenario={scenario} name={name}".format(
                    bk_biz_id=c.bk_biz_id,
                    cid=c.collector_config_id,
                    scenario=c.collector_scenario_id,
                    name=c.collector_config_name,
                )
            )

        if dry_run:
            Prompt.info(msg="dry-run 模式：仅打印，不执行实际停用操作")
            return

        if not skip_confirm:
            answer = input("\n以上采集项将被停用（卸载子配置），是否继续？输入 yes 确认: ").strip().lower()
            if answer not in ("yes", "y"):
                Prompt.warning(msg="已取消操作")
                return

        # 以 admin 身份执行，避免 stop() 内获取请求用户失败
        activate_request(generate_request("admin"))

        success_ids = []
        failed_items = []

        for c in collectors:
            cid = c.collector_config_id
            try:
                CollectorHandler.get_instance(cid).stop(is_stop_index_set=is_stop_index_set)
                success_ids.append(cid)
                Prompt.info(msg="停用成功: id={cid} name={name}", cid=cid, name=c.collector_config_name)
            except Exception as e:  # pylint: disable=broad-except
                failed_items.append((cid, str(e)))
                Prompt.error(
                    msg="停用失败: id={cid} name={name}, 错误: {error}",
                    cid=cid,
                    name=c.collector_config_name,
                    error=str(e),
                )

        Prompt.info(
            msg="\n停用完成 -> 成功 {ok} 个，失败 {fail} 个\n成功列表: {success_ids}",
            ok=len(success_ids),
            fail=len(failed_items),
            success_ids=success_ids,
        )
        if failed_items:
            Prompt.error(
                msg="失败列表（采集项ID: 错误原因）:\n{details}",
                details="\n".join([f"  - {cid}: {err}" for cid, err in failed_items]),
            )


class PromptColorEnum:
    """提示颜色枚举"""

    DEBUG = "cyan"
    INFO = "green"
    WARNING = "blue"
    ERROR = "red"
    PANIC = "red"


class Prompt:
    """提示"""

    COLORS = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "reset": "\033[0m",
    }

    @classmethod
    def print(cls, msg, **kwargs):
        if kwargs:
            for key, value in kwargs.items():
                msg = msg.replace(f"{{{key}}}", f"{value}")
        print(msg)

    @classmethod
    def fprint(cls, level: str, msg, **kwargs):
        color = cls.COLORS[PromptColorEnum.__dict__[level.upper()]]
        msg = f"{color}[{level.upper()}]{cls.COLORS['reset']}\t" + msg
        if kwargs:
            for key, value in kwargs.items():
                msg = msg.replace(f"{{{key}}}", f"{color}{value}{cls.COLORS['reset']}")
        print(msg)

    @classmethod
    def info(cls, msg, **kwargs):
        cls.fprint("info", msg, **kwargs)

    @classmethod
    def warning(cls, msg, **kwargs):
        cls.fprint("warning", msg, **kwargs)

    @classmethod
    def error(cls, msg, **kwargs):
        cls.fprint("error", msg, **kwargs)

    @classmethod
    def panic(cls, msg, **kwargs):
        cls.fprint("panic", msg, **kwargs)
        sys.exit(1)
