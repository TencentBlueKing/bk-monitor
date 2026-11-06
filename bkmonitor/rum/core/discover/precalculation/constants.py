"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

RUM 预计算表（session / view）的 schema 与配置常量。

字段定义以设计文档为准：
- docs/pre/Precalculate-index-fields.md

参考实现：
- bkmonitor/apm/core/discover/precalculation/storage.py  PrecalculateStorage（5 张共享表 + RendezvousHash 路由）
- bkmonitor/constants/apm.py                            PrecalculateStorageConfig / ApmGlobalTablePrefix
"""

from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.common_utils import count_md5


def _flatten_field_groups(*groups):
    """将多个 (field_name, field_type, tag, option, description) 元组展开为 schema 列表。

    RumPrecalculateStorageConfig 内的 _COMMON_*_FIELDS / _VIEW_SPECIFIC_FIELDS /
    _SESSION_SPECIFIC_FIELDS 都是这类 5 元组的元组，本函数负责拼接为 ResultTable 接受的
    字典列表。
    """
    schema: list[dict] = []
    for group in groups:
        for field_name, field_type, tag, option, description in group:
            schema.append(
                {
                    "field_name": field_name,
                    "field_type": field_type,
                    "tag": tag,
                    "option": option,
                    "is_config_by_user": True,
                    "description": description,
                }
            )
    return schema


class RumGlobalTablePrefix:
    """RUM 预计算结果表全局表名前缀。

    最终 ES 索引 pattern：
    - rum_global_session_precalculate_auto_{1..N}
    - rum_global_view_precalculate_auto_{1..N}

    按 application_id rendezvous hash 路由到其中一张；
    写入时 document_id = attributes.session.id / attributes.view.id（覆盖式 upsert）。
    """

    PRECALCULATE_SESSION = "rum_global_session_precalculate"
    PRECALCULATE_VIEW = "rum_global_view_precalculate"


class CommonDimensionField:
    """公共维度字段（View / Session 两表共享），OTel 嵌套路径风格。

    类型细分：
    - keyword 类：bk_biz_id / app_name / attributes.session.id / attributes.user.id /
                  resource.* / resource.user_agent.* / resource.device.type /
                  attributes.network.effective_type / close_reason
    - boolean 类：attributes.session.has_replay / closed / is_active
    """

    # 业务 / 应用维度
    BK_BIZ_ID = "bk_biz_id"
    APP_NAME = "app_name"

    # OTel attributes.*
    SESSION_ID = "attributes.session.id"
    USER_ID = "attributes.user.id"
    HAS_REPLAY = "attributes.session.has_replay"
    NETWORK_EFFECTIVE_TYPE = "attributes.network.effective_type"

    # OTel resource.service.*
    SERVICE_NAME = "resource.service.name"
    SERVICE_VERSION = "resource.service.version"

    # OTel resource.deployment.*
    DEPLOY_ENV = "resource.deployment.environment.name"

    # OTel resource.telemetry.*
    SDK_NAME = "resource.telemetry.sdk.name"
    SDK_LANGUAGE = "resource.telemetry.sdk.language"
    SDK_VERSION = "resource.telemetry.sdk.version"

    # OTel resource.user_agent.*
    BROWSER_NAME = "resource.user_agent.name"
    BROWSER_VERSION = "resource.user_agent.version"
    OS_NAME = "resource.user_agent.os.name"
    DEVICE_TYPE = "resource.device.type"

    # 窗口关闭元数据
    CLOSED = "closed"
    IS_ACTIVE = "is_active"
    CLOSE_REASON = "close_reason"


class CommonMetricField:
    """公共指标字段（View / Session 两表共享）。

    类型细分：
    - long（纯计数）：action_count / resource_count / error_count / request_count /
                     long_task_count / frustration_count
    - long（耗时 µs）：duration / attributes.view.loading_time
    - integer（计数）：trace_count / request_error_count
    """

    ACTION_COUNT = "action_count"
    RESOURCE_COUNT = "resource_count"
    ERROR_COUNT = "error_count"
    REQUEST_COUNT = "request_count"
    REQUEST_ERROR_COUNT = "request_error_count"
    LONG_TASK_COUNT = "long_task_count"
    TRACE_COUNT = "trace_count"
    FRUSTRATION_COUNT = "frustration_count"

    DURATION = "duration"
    VIEW_LOADING_TIME = "attributes.view.loading_time"


class CommonTimestampField:
    """公共时间戳维度字段（long + unit=microsecond）。

    - time: 文档写入时间，由公共 Emitter 统一补充
    - updated_at_ts: 本次快照更新时间
    - close_time: 窗口关闭时间（增量快照为 0）
    - min_start_time: View 取 SDK 上报的 view.started_at，Session 取会话内最早事件时间
    - max_end_time: 聚合对象内最晚事件时间
    - date: min_start_time 对应的 UTC 日期，格式 yyyy-MM-dd，用于日索引命名与按天筛选
    """

    TIME = "time"
    UPDATED_AT_TS = "updated_at_ts"
    CLOSE_TIME = "close_time"
    MIN_START_TIME = "min_start_time"
    MAX_END_TIME = "max_end_time"
    DATE = "date"


class CommonWebVitalsField:
    """公共 Web Vitals 字段（View / Session 两表共享，仅 lcp/inp/cls）。

    Session 中 lcp/inp 为"会话内最大值"，cls 为"会话内最大值"，view.loading_time 为"会话内平均"。

    - long（耗时 µs）：lcp / inp
    - double：cls
    """

    LCP = "web_vitals.lcp"
    INP = "web_vitals.inp"
    CLS = "web_vitals.cls"


class ViewSpecificField:
    """View 专属字段。

    类型细分：
    - keyword：attributes.view.* / view_loading_time_source / end_reason
    - date（yyyy-MM-dd）：view_date（View 开始时间对应的 UTC 日期）
    - long（耗时 µs）：web_vitals.fcp / web_vitals.ttfb / view_started_at
    """

    VIEW_ID = "attributes.view.id"
    VIEW_NAME = "attributes.view.name"
    VIEW_URL_TEMPLATE = "attributes.view.url_template"
    VIEW_LOADING_TYPE = "attributes.view.loading_type"
    VIEW_PREVIOUS_URL_TEMPLATE = "attributes.view.previous_url_template"
    VIEW_LOADING_TIME_SOURCE = "view_loading_time_source"
    END_REASON = "end_reason"
    VIEW_DATE = "view_date"

    FCP = "web_vitals.fcp"
    TTFB = "web_vitals.ttfb"

    VIEW_STARTED_AT = "view_started_at"


class SessionSpecificField:
    """Session 专属字段。

    类型细分：
    - long（耗时 µs）：session_start_ts / session_end_ts
    - keyword：enter_url_template / exit_url_template

    注：date 字段已在公共维度字段中通过 CommonTimestampField.DATE 统一定义，
        Session 无需单独列出。
    """

    SESSION_START_TS = "session_start_ts"
    SESSION_END_TS = "session_end_ts"

    ENTER_URL_TEMPLATE = "enter_url_template"
    EXIT_URL_TEMPLATE = "exit_url_template"


# session / view 两表 result_table.option
# need_add_time=True 表示按时间范围指定具体日期的索引进行查询。
RUM_PRECALCULATE_RESULT_TABLE_OPTION = {
    "need_add_time": True,
}


class RumPrecalculateStorageConfig:
    """RUM 预计算表的字段定义。

    字段集与 docs/pre/Precalculate-index-fields.md 一一对应；
    字段命名遵循 OTel 嵌套路径（如 attributes.session.id、web_vitals.lcp）。
    """

    # ---- field_type 常量（ResultTableField 已支持 string/int/long/boolean，
    #      double/date 由本类扩展，对应 ES 端的 es_type） ----
    FIELD_TYPE_STRING = "string"
    FIELD_TYPE_INT = "int"
    FIELD_TYPE_LONG = "long"
    FIELD_TYPE_DOUBLE = "double"
    FIELD_TYPE_BOOLEAN = "boolean"
    FIELD_TYPE_DATE = "date"

    # ---- tag 常量 ----
    TAG_DIMENSION = "dimension"
    TAG_METRIC = "metric"

    # ---- ES option 模板 ----
    # 警告：以下 7 个 dict 是类属性，所有字段直接共享同一字典对象引用。
    # 若需就地修改某个字段的 option（例如 field['option']['es_type'] = 'text'），
    # 会污染所有引用同一个 OPT_* 的字段。请改为 dict(OPT_KEYWORD) 复制后再修改。
    OPT_KEYWORD = {"es_type": "keyword"}
    OPT_BOOLEAN = {"es_type": "boolean"}
    OPT_DATE = {"es_type": "date", "es_format": "yyyy-MM-dd"}
    OPT_DOUBLE = {"es_type": "double"}
    OPT_LONG = {"es_type": "long"}
    OPT_LONG_US = {"es_type": "long", "unit": "microsecond"}
    OPT_INT = {"es_type": "integer"}

    # ============================================================
    # 公共字段（两表共享）—— 顺序与文档「View 和 Session 公共字段」表一致
    # ============================================================

    # keyword / boolean / date 维度
    _COMMON_DIMENSION_FIELDS = (
        (CommonDimensionField.BK_BIZ_ID, FIELD_TYPE_INT, TAG_DIMENSION, OPT_INT, "蓝鲸业务 ID"),
        (CommonDimensionField.APP_NAME, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "RUM 应用名称"),
        (CommonDimensionField.SESSION_ID, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "Session ID"),
        (CommonDimensionField.USER_ID, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "用户 ID"),
        (CommonDimensionField.HAS_REPLAY, FIELD_TYPE_BOOLEAN, TAG_DIMENSION, OPT_BOOLEAN, "Session 是否包含回放"),
        (CommonDimensionField.SERVICE_NAME, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "服务名称"),
        (CommonDimensionField.SERVICE_VERSION, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "服务版本"),
        (CommonDimensionField.DEPLOY_ENV, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "部署环境"),
        (CommonDimensionField.SDK_NAME, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "Telemetry SDK 名称"),
        (CommonDimensionField.SDK_LANGUAGE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "Telemetry SDK 语言"),
        (CommonDimensionField.SDK_VERSION, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "Telemetry SDK 版本"),
        (CommonDimensionField.BROWSER_NAME, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "浏览器名称"),
        (CommonDimensionField.BROWSER_VERSION, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "浏览器版本"),
        (CommonDimensionField.OS_NAME, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "操作系统名称"),
        (CommonDimensionField.DEVICE_TYPE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "设备类型"),
        (CommonDimensionField.NETWORK_EFFECTIVE_TYPE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "有效网络质量"),
        (CommonDimensionField.CLOSED, FIELD_TYPE_BOOLEAN, TAG_DIMENSION, OPT_BOOLEAN, "是否为最终关闭快照"),
        (CommonDimensionField.IS_ACTIVE, FIELD_TYPE_BOOLEAN, TAG_DIMENSION, OPT_BOOLEAN, "是否仍处于活动窗口"),
        (CommonDimensionField.CLOSE_REASON, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "平台派生的窗口关闭原因"),
        (CommonTimestampField.MIN_START_TIME, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "开始时间，View 取 view.started_at，Session 取会话内最早事件时间"),
        (CommonTimestampField.MAX_END_TIME, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "聚合对象内最晚事件时间"),
        (CommonTimestampField.DATE, FIELD_TYPE_DATE, TAG_DIMENSION, OPT_DATE, "min_start_time 对应的 UTC 日期，格式 yyyy-MM-dd"),
    )

    # long / integer / double 指标
    _COMMON_METRIC_FIELDS = (
        (CommonMetricField.ACTION_COUNT, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG, "Action / Click 事件数量"),
        (CommonMetricField.RESOURCE_COUNT, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG, "Resource 事件总数"),
        (CommonMetricField.ERROR_COUNT, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG, "错误类事件数量"),
        (CommonMetricField.REQUEST_COUNT, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG, "XHR / Fetch 请求数量"),
        (CommonMetricField.REQUEST_ERROR_COUNT, FIELD_TYPE_INT, TAG_METRIC, OPT_INT, "XHR / Fetch 错误或超时数量"),
        (CommonMetricField.LONG_TASK_COUNT, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG, "Long Task 事件数量"),
        (CommonMetricField.FRUSTRATION_COUNT, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG, "挫败行为数量"),
        (CommonMetricField.TRACE_COUNT, FIELD_TYPE_INT, TAG_METRIC, OPT_INT, "Span Link 数量"),
        (CommonMetricField.DURATION, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG_US, "聚合对象持续时长 µs"),
        (CommonMetricField.VIEW_LOADING_TIME, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG_US, "View 加载耗时 µs"),
    )

    # long 时间戳维度（µs）—— time 字段由公共 Emitter 统一补充，不参与 schema 检测
    _COMMON_TIMESTAMP_FIELDS = (
        (CommonTimestampField.TIME, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "文档写入时间"),
        (CommonTimestampField.UPDATED_AT_TS, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "本次快照更新时间"),
        (CommonTimestampField.CLOSE_TIME, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "窗口关闭时间"),
    )

    # web_vitals 系列（lcp/inp/cls 三项两表共享）
    _COMMON_WEB_VITALS_FIELDS = (
        (CommonWebVitalsField.LCP, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG_US, "LCP 指标 µs"),
        (CommonWebVitalsField.INP, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG_US, "INP 指标 µs"),
        (CommonWebVitalsField.CLS, FIELD_TYPE_DOUBLE, TAG_METRIC, OPT_DOUBLE, "CLS 指标"),
    )

    # ============================================================
    # View 专属字段 —— 顺序与文档「View 专属字段」表一致
    # ============================================================
    _VIEW_SPECIFIC_FIELDS = (
        (ViewSpecificField.VIEW_ID, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "View ID（文档主键）"),
        (ViewSpecificField.VIEW_NAME, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "View 名称"),
        (ViewSpecificField.VIEW_URL_TEMPLATE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "View URL 路径模板"),
        (ViewSpecificField.VIEW_LOADING_TYPE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "View 加载类型"),
        (ViewSpecificField.VIEW_PREVIOUS_URL_TEMPLATE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "前一个 View URL 模板"),
        (ViewSpecificField.VIEW_LOADING_TIME_SOURCE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "View 加载耗时来源"),
        (ViewSpecificField.END_REASON, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "SDK 原始 view.end_reason"),
        (ViewSpecificField.VIEW_DATE, FIELD_TYPE_DATE, TAG_DIMENSION, OPT_DATE, "View 开始时间对应的 UTC 日期"),
        (ViewSpecificField.FCP, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG_US, "FCP 指标 µs"),
        (ViewSpecificField.TTFB, FIELD_TYPE_LONG, TAG_METRIC, OPT_LONG_US, "TTFB 指标 µs"),
        (ViewSpecificField.VIEW_STARTED_AT, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "View 开始时间 µs"),
    )

    # ============================================================
    # Session 专属字段 —— 顺序与文档「Session 专属字段」表一致
    # ============================================================
    _SESSION_SPECIFIC_FIELDS = (
        (SessionSpecificField.SESSION_START_TS, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "Session 内最早事件时间 µs"),
        (SessionSpecificField.SESSION_END_TS, FIELD_TYPE_LONG, TAG_DIMENSION, OPT_LONG_US, "Session 内最晚事件时间 µs"),
        (SessionSpecificField.ENTER_URL_TEMPLATE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "Session 入口 View URL 模板"),
        (SessionSpecificField.EXIT_URL_TEMPLATE, FIELD_TYPE_STRING, TAG_DIMENSION, OPT_KEYWORD, "Session 退出 View URL 模板"),
    )

    # ============================================================
    # 派生完整 schema
    # ============================================================

    SESSION_TABLE_SCHEMA: list[dict] = _flatten_field_groups(
        _COMMON_DIMENSION_FIELDS,
        _COMMON_METRIC_FIELDS,
        _COMMON_TIMESTAMP_FIELDS,
        _COMMON_WEB_VITALS_FIELDS,
        _SESSION_SPECIFIC_FIELDS,
    )

    VIEW_TABLE_SCHEMA: list[dict] = _flatten_field_groups(
        _COMMON_DIMENSION_FIELDS,
        _COMMON_METRIC_FIELDS,
        _COMMON_TIMESTAMP_FIELDS,
        _COMMON_WEB_VITALS_FIELDS,
        _VIEW_SPECIFIC_FIELDS,
    )

    # Modify/CreateResultTable 与 QueryResultTable 接口返回的字段命名差异
    RESULT_TABLE_FIELD_MAPPING = {
        "field_name": "field_name",
        "type": "field_type",
        "tag": "tag",
        "option": "option",
    }

    # 字段变更检测要关注的列
    CHECK_UPDATE_FIELDS = ["field_name", "field_type", "tag", "option"]

    @classmethod
    def get_table_schema(cls, table_kind: str) -> list[dict]:
        if table_kind == "session":
            # 返回拷贝，避免调用方就地修改污染类属性上的 schema
            return list(cls.SESSION_TABLE_SCHEMA)
        if table_kind == "view":
            return list(cls.VIEW_TABLE_SCHEMA)
        raise ValueError(_("未知的 RUM 预计算 table_kind: {}").format(table_kind))

    @classmethod
    def get_table_schema_md5(cls, table_kind: str) -> str:
        import json

        return count_md5(json.dumps(cls._exact_unique_data(cls.get_table_schema(table_kind)), sort_keys=True))

    @classmethod
    def _exact_unique_data(cls, data: list[dict]) -> dict[str, dict]:
        res = {}
        for i in data:
            res[i["field_name"]] = {k: i.get(k) for k in cls.CHECK_UPDATE_FIELDS}
        # 移除 time 字段（由公共 Emitter 统一补充，schema 检测不需要它）
        res.pop(CommonTimestampField.TIME, None)
        return res
