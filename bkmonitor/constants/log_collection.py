"""日志采集 MCP 公共常量。"""

ETL_CONFIG_TEXT = "bk_log_text"
ETL_CONFIG_JSON = "bk_log_json"
ETL_CONFIG_DELIMITER = "bk_log_delimiter"
ETL_CONFIG_REGEXP = "bk_log_regexp"

SUPPORTED_ETL_PREVIEW_CONFIGS = (
    ETL_CONFIG_TEXT,
    ETL_CONFIG_JSON,
    ETL_CONFIG_DELIMITER,
    ETL_CONFIG_REGEXP,
)

# 预览只接受一条有限长度的样例，避免把 MCP 当作批量清洗入口。
ETL_PREVIEW_MAX_SAMPLE_LENGTH = 10_000
# 限制返回字段数量，避免 JSON、正则或分隔符生成过大的 Tool 响应。
ETL_PREVIEW_MAX_FIELDS = 100
# 正则/Grok 表达式会进入清洗引擎，单独限制嵌套参数，而非仅限制请求体大小。
ETL_PREVIEW_MAX_EXPRESSION_LENGTH = 4_096
ETL_PREVIEW_MAX_SEPARATOR_LENGTH = 128
