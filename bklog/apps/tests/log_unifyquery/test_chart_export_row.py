from django.test import SimpleTestCase

from apps.utils.function import project_chart_row


class TestProjectChartRow(SimpleTestCase):
    """图表导出行投影：兼容扁平与嵌套两种字段形态"""

    def test_flat_record_direct_hit(self):
        record = {"body.player.id": "12345", "message": "hello"}
        self.assertEqual(project_chart_row(record, ["body.player.id", "message"]), ["12345", "hello"])

    def test_nested_record_path_navigation(self):
        record = {"body": {"player": {"id": "1***5"}}}
        self.assertEqual(project_chart_row(record, ["body.player.id"]), ["1***5"])

    def test_missing_field_returns_empty(self):
        record = {"body": {"player": {}}}
        self.assertEqual(project_chart_row(record, ["body.player.id", "message"]), ["", ""])

    def test_none_value_preserved(self):
        self.assertEqual(project_chart_row({"a": None}, ["a"]), [None])
