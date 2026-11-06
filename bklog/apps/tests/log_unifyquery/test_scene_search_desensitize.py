# -*- coding: utf-8 -*-
"""
SceneUnifyQueryHandler 脱敏异常隔离测试。

覆盖：
- _deal_query_result 中单条 _log_desensitize 异常不中断同批其他日志
- export_chart_data 中单条 _log_desensitize 异常不终止 CSV 导出

遵循 AEP：
- 纯内存用例用 SimpleTestCase（无 DB 写入）
- 断言精确控制字段值与数量
"""
from contextlib import ExitStack
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler


def _build_minimal_handler(**kwargs):
    """构造一个不走 __init__ 的 SceneUnifyQueryHandler 裸实例，手动注入必要属性。"""
    handler = SceneUnifyQueryHandler.__new__(SceneUnifyQueryHandler)
    handler.is_desensitize = kwargs.get("is_desensitize", True)
    handler.field_configs = kwargs.get("field_configs", [{"field_name": "test"}])
    handler.text_fields_field_configs = kwargs.get("text_fields_field_configs", [])
    handler.text_fields = kwargs.get("text_fields", [])
    handler.desensitize_handler = kwargs.get("desensitize_handler", None)
    handler.text_fields_desensitize_handler = kwargs.get("text_fields_desensitize_handler", None)
    handler.export_fields = kwargs.get("export_fields", None)
    handler.highlight = kwargs.get("highlight", False)
    handler.log_bcs_cluster_name_dict = kwargs.get("log_bcs_cluster_name_dict", {})
    handler._desensitize_initialized = True
    return handler


class TestSceneUnifyQueryHandlerDesensitize(SimpleTestCase):
    """SceneUnifyQueryHandler 脱敏异常隔离测试"""

    def test_scene_desensitize_isolation(self):
        """_deal_query_result：单条 _log_desensitize 抛异常，同批其他日志正常处理"""
        handler = _build_minimal_handler()

        rogue_log = {"__doc_id": "rogue", "message": "should survive"}
        normal_log = {"__doc_id": "normal", "message": "should also survive"}

        with ExitStack() as stack:
            # 第一条日志脱敏抛异常，第二条正常返回
            stack.enter_context(
                patch.object(handler, "_log_desensitize", side_effect=[Exception("boom"), normal_log])
            )
            stack.enter_context(patch.object(handler, "_add_cmdb_fields", side_effect=lambda x: x))
            stack.enter_context(patch.object(handler, "_add_bcs_cluster_fields", side_effect=lambda x: x))

            result = handler._deal_query_result({"list": [rogue_log, normal_log]})

        # 两条日志都返回
        self.assertEqual(len(result["list"]), 2)
        # _deal_query_result 内部会把 __doc_id pop 为 __id__
        # 抛异常的那条仍保留原始值（未被脱敏但未丢失）
        rogue_result = [log for log in result["list"] if log.get("__id__") == "rogue"]
        self.assertEqual(len(rogue_result), 1)
        self.assertEqual(rogue_result[0]["message"], "should survive")
        # 正常日志正常处理
        normal_result = [log for log in result["list"] if log.get("__id__") == "normal"]
        self.assertEqual(len(normal_result), 1)

    def test_scene_desensitize_isolation_no_desensitize(self):
        """is_desensitize=False 时跳过脱敏，不触发 _log_desensitize"""
        handler = _build_minimal_handler(is_desensitize=False)

        log_entry = {"__doc_id": "skip", "message": "not desensitized"}

        with ExitStack() as stack:
            mock_desensitize = stack.enter_context(patch.object(handler, "_log_desensitize"))
            stack.enter_context(patch.object(handler, "_add_cmdb_fields", side_effect=lambda x: x))
            stack.enter_context(patch.object(handler, "_add_bcs_cluster_fields", side_effect=lambda x: x))

            result = handler._deal_query_result({"list": [log_entry]})

        self.assertEqual(len(result["list"]), 1)
        mock_desensitize.assert_not_called()

    def test_scene_desensitize_isolation_empty_list(self):
        """空 list 不崩溃"""
        handler = _build_minimal_handler()

        with ExitStack() as stack:
            stack.enter_context(patch.object(handler, "_add_cmdb_fields", side_effect=lambda x: x))
            stack.enter_context(patch.object(handler, "_add_bcs_cluster_fields", side_effect=lambda x: x))

            result = handler._deal_query_result({"list": []})

        self.assertEqual(len(result["list"]), 0)

    def test_scene_export_desensitize_isolation(self):
        """export_chart_data：单条 _log_desensitize 抛异常，不终止 CSV 导出"""
        handler = _build_minimal_handler()
        handler.base_dict = {}
        handler.is_desensitize = True

        rogue_record = {"__doc_id": "rogue_export", "message": "bad"}
        normal_record = {"__doc_id": "normal_export", "message": "good"}

        mock_scroll_result = {
            "list": [rogue_record, normal_record],
            "result_table_id": "test_rt",
            "done": True,
        }

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    handler, "query_ts_raw_with_scroll", return_value=mock_scroll_result
                )
            )
            stack.enter_context(patch.object(handler, "_init_scene_desensitize"))
            stack.enter_context(
                patch.object(
                    handler, "_log_desensitize",
                    side_effect=[Exception("export boom"), normal_record],
                )
            )

            # 消费生成器
            rows = list(handler.export_chart_data())

        # 应有输出（至少表头行 + 数据行）
        self.assertGreater(len(rows), 0)
