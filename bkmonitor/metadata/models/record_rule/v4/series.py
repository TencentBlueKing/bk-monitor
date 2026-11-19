"""下发前按完整表达式的即时输出数量检查 series 上限。"""

import time

from django.conf import settings

from core.drf_resource import api
from metadata.models.record_rule.constants import RecordRuleV4InputType
from metadata.models.record_rule.v4.models import RecordRuleV4, RecordRuleV4Resolved
from metadata.models.record_rule.v4.resolver import RecordRuleV4Resolver


def check_series_limit(rule: RecordRuleV4, resolved: RecordRuleV4Resolved) -> None:
    config = settings.RECORD_RULE_V4_CONFIG
    if rule.pk in config.get("series_exempt_rule_ids", []):
        return
    limit = config.get("max_series", 500000)
    if limit == 0:
        return
    timestamp = str(int(time.time()))
    resolver = RecordRuleV4Resolver(rule)
    for record in resolved.get_records():
        spec_record = record.spec_record
        context = f"规则组 {rule.name}，规则 {spec_record.metric_name}（{record.record_key}），语句 {record.metricql}"
        try:
            if spec_record.input_type == RecordRuleV4InputType.PROMQL.value:
                params = resolver.build_check_promql_params(spec_record.input_config)
                params.update(promql=f"count({params['promql']}\n)", start=timestamp, end=timestamp)
                query = api.unify_query.query_data_by_promql
            else:
                params = resolver.build_check_query_ts_params(spec_record.input_config)
                params.update(
                    metric_merge=f"count({params['metric_merge']}\n)",
                    start_time=timestamp,
                    end_time=timestamp,
                    down_sample_range="",
                    not_time_align=True,
                )
                query = api.unify_query.query_data
            params.update(bk_tenant_id=rule.bk_tenant_id, space_uid=rule.space_uid, instant=True)
            count = read_series_count(query(**params))
        except Exception as error:
            raise ValueError(f"{context}：series 数量测试失败，请重试。{error}") from error
        if count > limit:
            raise ValueError(
                f"{context}：输出 series 数量 {count} 超过阈值 {limit}，禁止下发。"
                "请联系监控管理员进行评估，获得许可后再下发。"
            )


def read_series_count(data: dict) -> int:
    """读取 count 即时查询的单个值；缺失或不完整响应不能当作零。"""
    status = data.get("status") or {}
    if data.get("is_partial") or status.get("is_partial") or status.get("series_limit_reached"):
        raise ValueError("查询返回不完整结果")
    series = data["series"]
    if series == []:
        return 0
    (table,) = series
    (sample,) = table["values"]
    value = float(sample[table["columns"].index("_value")])
    if not value.is_integer() or value < 0:
        raise ValueError("查询未返回有效的 series 数量")
    return int(value)
