import json

import arrow

from ai_agent.services.local_command_handler import (
    CommandHandler,
    local_command_handler,
)
from apps.log_unifyquery.builder.context import build_context_params
from apps.utils.log import logger
from bkm_space.utils import space_uid_to_bk_biz_id


@local_command_handler("log_analysis")
class LogAnalysisCommandHandler(CommandHandler):
    """
    日志分析命令处理器
    命令参数:
    - index_set_id: 索引集ID
    - log: 日志内容，为 dict 结构
    - context_count: 引用的上下文条数，默认为 10
    """

    # 基于 128K 上下文长度设置
    MAX_CHARACTER_LENGTH = 120_000

    FIELDS_EXCLUDED = {
        "__data_label",
        "__dist_05",
        "__id__",
        "__index_set_id__",
        "__parse_failure",
        "__result_table",
        "gseIndex",
        "iterationIndex",
        "time",
        "_time",
    }

    @classmethod
    def clean_context_log(cls, context_log: dict, log: dict) -> dict:
        """
        清理上下文日志中的重复 kv 对
        """
        for key in list(context_log.keys()):
            if key in cls.FIELDS_EXCLUDED:
                del context_log[key]
                continue

            if log.get(key) == context_log[key]:
                del context_log[key]

        return context_log

    def process_content(self, context: list[dict]) -> str:
        # 必须放到这里加载，否则 django 会因国际化加载失败
        from apps.log_search.models import LogIndexSet
        from apps.log_unifyquery.handler.context import UnifyQueryContextHandler

        template = self.get_template()
        variables = self.extract_context_vars(context)

        index_set_id = int(variables["index_set_id"])
        context_count = int(variables.get("context_count", 10))
        log = variables["log"]

        log_data = json.loads(log)
        for key in log_data.copy():
            if key in self.FIELDS_EXCLUDED:
                del log_data[key]

        index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if not index_set_obj:
            return self.jinja_env.render(template, {"log": json.dumps(log_data), "context": ""})

        params = json.loads(log)
        params.update(
            {
                "search_type_tag": "context",
                "index_set_id": index_set_id,
                "begin": 0,
                "size": context_count,
                "zero": True,
                "bk_biz_id": space_uid_to_bk_biz_id(index_set_obj.space_uid),
            }
        )

        params = build_context_params(params)

        context_logs = []
        try:
            query_handler = UnifyQueryContextHandler(params)
            context_result = query_handler.search()
            context_logs = context_result.get("origin_log_list") or []
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("context fetch failed, reason: %s, origin log: %s", e, log)

        total_character_length = len(log)

        final_context_logs = []

        for index, context_log in enumerate(context_logs):
            # 在模型上下文内容大小限制的前提下，尽可能多的引用日志上下文
            if total_character_length > self.MAX_CHARACTER_LENGTH:
                break

            # 去掉与原始日志完全一致的 kv 对，精简上下文内容大小
            if index > 0:
                cleaned_context_log = self.clean_context_log(context_log, context_logs[0])
                if not cleaned_context_log:
                    continue
            else:
                cleaned_context_log = context_log
            cleaned_context_log = json.dumps(cleaned_context_log)
            final_context_logs.append(cleaned_context_log)
            total_character_length += len(cleaned_context_log)

        return self.jinja_env.render(template, {"log": json.dumps(log_data), "context": "\n".join(final_context_logs)})

    def get_template(self) -> str:
        return """## 日志内容开始
{{ log }}
## 日志内容结束 ##
## 上下文内容开始 ##
{{ context }}
## 上下文内容结束 ##
        """


@local_command_handler("querystring_generate")
class QuerystringGenerateCommandHandler(CommandHandler):
    """
    生成查询语句命令处理器
    """

    @classmethod
    def _get_index_set_fields(cls, index_set_id: int) -> dict:
        """
        获取索引集的字段信息

        Args:
            index_set_id: 索引集ID

        Returns:
            dict: 字段信息字典，格式为 {field_name: {type: str, query_alias?: str}}
        """
        from apps.log_search.models import LogIndexSet

        index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if not index_set_obj:
            return {}

        fields_info = index_set_obj.get_fields(use_snapshot=True)
        if not fields_info.get("fields"):
            return {}

        fields = {}
        for field_info in fields_info.get("fields"):
            field_data = {"type": field_info["field_type"]}
            if field_info.get("query_alias"):
                field_data["query_alias"] = field_info["query_alias"]
            fields[field_info["field_name"]] = field_data

        return fields

    def process_content(self, context: list[dict]) -> str:
        template = self.get_template()
        variables = self.extract_context_vars(context)

        current_datetime = arrow.now().floor("minute").format("YYYY-MM-DD HH:mm:ss")

        return self.jinja_env.render(
            template,
            {
                "description": variables["description"],
                "fields": variables.get("fields", "{}"),
                "domain": variables["domain"],
                "index_set_id": variables["index_set_id"],
                "current_datetime": current_datetime,
            },
        )

    def get_template(self) -> str:
        return """
## 检索需求
{{ description }}

## 字段信息
{{ fields }}

## 平台域名
{{ domain }}

## 索引集ID
{{ index_set_id }}

## 当前时间
{{ current_datetime }}
        """


@local_command_handler("querystring_generate_json")
class QuerystringGenerateJSONCommandHandler(QuerystringGenerateCommandHandler):
    """
    生成查询语句命令处理器 (JSON结构化版本)
    """

    pass


@local_command_handler("clustering_regex_generate")
class ClusteringRegexGenerateCommandHandler(CommandHandler):
    """
    聚类正则生成命令处理器
    通过 signature 查询同类日志，提供多条同结构日志样本给 LLM，生成更精准的正则表达式

    命令参数:
    - index_set_id: 索引集ID
    - signature: 数据指纹 (聚类签名)
    - origin_log: 原始日志内容
    - target_text: 用户选中的待匹配文本片段
    - pattern_level: 聚类敏感度等级，默认为 "05"
    """

    # 查询同类日志的最大条数
    MAX_SAMPLE_COUNT = 10
    # 查询同类日志的默认时间范围（天）
    DEFAULT_QUERY_DAYS = 1

    def _query_same_signature_logs(
        self,
        index_set_id: int,
        signature: str,
        aggs_field: str,
        bk_biz_id: int,
    ) -> list[dict]:
        """
        查询与给定 signature 相同的日志，返回日志内容列表
        """
        from apps.log_unifyquery.handler.base import UnifyQueryHandler

        end_time = arrow.now().int_timestamp * 1000
        start_time = arrow.now().shift(days=-self.DEFAULT_QUERY_DAYS).int_timestamp * 1000

        params = {
            "keyword": "*",
            "addition": [{"field": aggs_field, "operator": "is", "value": signature}],
            "begin": 0,
            "size": self.MAX_SAMPLE_COUNT,
            "bk_biz_id": bk_biz_id,
            "index_set_ids": [index_set_id],
            "start_time": start_time,
            "end_time": end_time,
        }

        try:
            result = UnifyQueryHandler(params).search()
            return result.get("list", [])
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Failed to query same signature logs for index_set_id=%s, signature=%s, reason: %s",
                index_set_id,
                signature,
                e,
            )
            return []

    def process_content(self, context: list[dict]) -> str:
        from apps.log_clustering.models import ClusteringConfig
        from apps.log_clustering.constants import AGGS_FIELD_PREFIX

        template = self.get_template()
        variables = self.extract_context_vars(context)

        index_set_id = int(variables["index_set_id"])
        signature = variables["signature"]
        origin_log = variables.get("origin_log", "")
        target_text = variables.get("target_text", "")
        pattern_level = variables.get("pattern_level", "05")

        # 获取聚类配置
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id, raise_exception=False)
        if not clustering_config:
            logger.warning("ClusteringConfig not found for index_set_id=%s", index_set_id)
            return self.jinja_env.render(
                template,
                {
                    "origin_log": origin_log,
                    "target_text": target_text,
                    "sample_logs": "",
                },
            )

        aggs_field = "signature" if clustering_config.use_mini_link else f"{AGGS_FIELD_PREFIX}_{pattern_level}"

        # 查询同类日志（最多 10 条）
        sample_logs = self._query_same_signature_logs(
            index_set_id=index_set_id,
            signature=signature,
            aggs_field=aggs_field,
            bk_biz_id=clustering_config.bk_biz_id,
        )

        # 去重并排除原始日志
        seen = {origin_log}
        unique_samples = []
        for item in sample_logs:
            log_content = item.get(clustering_config.clustering_fields, "")
            if log_content in seen:
                continue
            seen.add(log_content)
            unique_samples.append(log_content)

        sample_logs_text = "\n".join(f"[样本 {i + 1}] {log}" for i, log in enumerate(unique_samples))

        return self.jinja_env.render(
            template,
            {
                "origin_log": origin_log,
                "target_text": target_text,
                "sample_logs": sample_logs_text,
            },
        )

    def get_template(self) -> str:
        return """
## 原始日志
{{ origin_log }}

## 待匹配字符串
{{ target_text }}

## 参考日志列表
{{ sample_logs }}
        """
