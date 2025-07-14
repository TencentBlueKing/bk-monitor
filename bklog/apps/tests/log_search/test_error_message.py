from django.test import TestCase
import logging
from apps.log_search.exceptions import (
    ESQuerySyntaxException,
    HighlightException,
    NoMappingException,
    UnsupportedOperationException,
    QueryServerUnavailableException,
    LogSearchException,
)
from apps.log_search.utils import handle_es_query_error


class TestESExceptionHandler(TestCase):
    def setUp(self):
        # 禁用日志输出，避免测试时打印过多信息
        logging.disable(logging.CRITICAL)

    def test_handle_es_query_syntax_error(self):
        # 测试查询语法错误模式
        error_messages = [
            '查询DSL错误, ERROR DSL is : "__ext.io_kubernetes_pod:trade* AND log:error AND log:"',
            "EsClient查询错误\"RequestError(400, 'search_phase_execution_exception', 'token_mgr_error: Lexical error at line 1, column 53. Encountered: <EOF> after : \"/zonesvr*\"')",
            'Failed to parse query ["32221112" AND path: /data/ test/user00/log/zonesvr*]',
        ]
        for msg in error_messages:
            with self.subTest(msg=msg):
                with self.assertRaises(ESQuerySyntaxException):
                    handle_es_query_error(Exception(msg))

    def test_handle_no_mapping_error(self):
        # 测试字段映射缺失错误
        error_msg = "No mapping found for [test_field] in order to sort on"
        with self.assertRaises(NoMappingException) as cm:
            handle_es_query_error(Exception(error_msg))
        self.assertIn("test_field", str(cm.exception))

    def test_handle_highlight_error(self):
        # 测试高亮失败错误
        error_messages = [
            "The length of [log] field of [27209] doc of [test_log_2025070302] index has exceeded [1000000] - maximum allowed to be analyzed for highlighting.",
            "The length [4580567] of field [log] in doc[50402]/index[test_server_log_20250622_0] exceeds the [index.highlight.max_analyzed_offset] limit [1000000].",
        ]
        for msg in error_messages:
            with self.subTest(msg=msg):
                with self.assertRaises(HighlightException) as cm:
                    handle_es_query_error(Exception(msg))
                self.assertIn("log", str(cm.exception))

    def test_handle_unsupported_operation_error(self):
        # 测试不支持的操作错误
        error_messages = [
            "Can't load fielddata on [test_field] because fielddata is unsupported on fields of type [keyword]. Use doc values instead.",
            "Fielddata is disabled on text fields by default. Set fielddata=true on [test_field] in order to load fielddata in memory by uninverting the inverted index.",
        ]
        for msg in error_messages:
            with self.subTest(msg=msg):
                with self.assertRaises(UnsupportedOperationException) as cm:
                    handle_es_query_error(Exception(msg))
                self.assertIn("test_field", str(cm.exception))

    def test_handle_server_unavailable_error(self):
        # 测试服务器不可用错误
        error_messages = [
            "HTTPConnectionPool(host='www.example.com', port=80): Read timed out. (read timeout=130)",
            "request_id [9034563563] timed out after [30012ms]",
            "[][] connect_timeout[30s]",
        ]
        for msg in error_messages:
            with self.subTest(msg=msg):
                with self.assertRaises(QueryServerUnavailableException):
                    handle_es_query_error(Exception(msg))

    def test_raw_error(self):
        # 测试没有匹配到任何错误模式
        error_messages = [
            'Enhanced lucene query string from ["日志检索异常" AND ("error")] to ["日志检索异常" AND ("error")]',
            "max_bytes_length_exceeded_exception: bytes can be at most 1024 in length; got 2048",
        ]
        for msg in error_messages:
            with self.subTest(msg=msg):
                with self.assertRaises(LogSearchException):
                    handle_es_query_error(Exception(msg))
