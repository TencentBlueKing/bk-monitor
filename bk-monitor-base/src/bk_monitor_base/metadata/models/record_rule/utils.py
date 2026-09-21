import logging
import re
from typing import Any

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.errors import BkApiError

logger = logging.getLogger("metadata")


def generate_table_id(space_type: str, space_id: str, record_name: str) -> str:
    """生成项目下的结果表"""
    # 处理预计算的名称
    # 替换`.`|`-`|`/`为`_`, 符合标准
    # 限制长度为110，因为限制的结果表长度为128
    space_id = space_id.replace(".", "_").replace("-", "_").replace("/", "_").strip("_")[:110]
    record_name = record_name.replace(".", "_").replace("-", "_").replace("/", "_").strip("_")[:110]
    return f"bkmonitor_{space_type}_{space_id}_{record_name}.__default__"


def sanitize(name: str, max_length: int = 110) -> str:
    """
    清理名称，替换非法字符并处理命名规则：
    - 替换非法字符 (.、-、/) 为 _
    - 避免连续的下划线 (_ -> 单个_)
    - 去掉首尾的下划线
    - 限制长度为 max_length
    - 确保符合 Prometheus 的指标正则规则 [a-zA-Z_:][a-zA-Z0-9_:]*
    """
    # 替换非法字符 (.、-、/) 为 _
    name = re.sub(r"[.\-\/]+", "_", name)
    # 合并连续的下划线为一个
    name = re.sub(r"_+", "_", name)
    # 去掉首尾的下划线
    name = name.strip("_")
    # 限制长度
    name = name[:max_length]
    # 确保不以非法字符结尾，若存在则去除
    while name and not re.match(r"[a-zA-Z0-9_:]$", name[-1]):
        name = name[:-1]
    # 校验最终结果是否符合 Prometheus 的正则规则
    if not re.match(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$", name):
        raise ValueError(f"Name '{name}' does not conform to naming rules")
    return name


def generate_pre_cal_table_id(space_type: str, space_id: str, record_name: str) -> str:
    """
    生成符合命名规范的预计算结果表ID
    命名规则：bkprecal_{space_type}_{space_id}_{record_name}.__default__
    @param space_type: 空间类型
    @param space_id: 空间ID
    @param record_name: 预计算规则名称
    @return: 预计算结果表ID
    """
    need_sanitize_name = f"bkprecal_{space_type}_{space_id}_{record_name}"
    table_id_prefix = sanitize(name=need_sanitize_name, max_length=110)
    return f"{table_id_prefix}.__default__"


def transform_record_to_metric_name(record: str) -> str:
    """转换预计算的record到指标名称
    record: "level:src_metric:operation"
    metric_name: "level_src_metric_operation"
    """
    return "_".join(record.strip(":").split(":")).strip("_")


def refine_bk_sql_and_metrics(promql: str, all_rule_record: list[str]) -> dict[str, Any]:
    """转换promql为sql语句，并且提取指标"""
    # 去掉注释
    promql_without_comment = re.sub(r"#.*", "", promql)
    # 去掉换行符
    _promql = promql_without_comment.replace("\n", " ")
    # 查找替换为新的指标
    for record in all_rule_record:
        if record not in _promql:
            continue
        _promql = _promql.replace(record, transform_record_to_metric_name(record))
    # 转换为结构体
    try:
        rule_dict = api.unify_query.promql_to_struct(bk_tenant_id=DEFAULT_TENANT_ID, params={"promql": _promql})
    except BkApiError as e:
        logger.error("transform promql to struct failed, promql: %s, error: %s", _promql, e)
        raise

    # 获取已有的指标，
    metrics = set()
    rule_data = rule_dict["data"]
    for item in rule_data["query_list"]:
        metrics.add(item["field_name"])
    # 在转换为promql
    try:
        sql = api.unify_query.struct_to_promql(bk_tenant_id=DEFAULT_TENANT_ID, params=rule_data)
    except BkApiError as e:
        logger.error("transform struct to promql failed, struct: %s, error: %s", rule_data, e)
        raise
    # 去掉`bkmonitor:`
    return {"promql": sql["promql"].replace("bkmonitor:", ""), "metrics": metrics}


def compose_rule_table_id(table_id: str) -> str:
    """生成规则表的名称"""
    if table_id.endswith("__default__"):
        table_id = table_id.split(".__default__")[0]
    name = f"{table_id.replace('-', '_').replace('.', '_').replace('__', '_')[-40:]}"
    # NOTE: 清洗结果表不能出现双下划线
    return f"vm_{name.strip('_')}"
