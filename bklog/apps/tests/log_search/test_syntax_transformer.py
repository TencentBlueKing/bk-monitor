import unittest

from apps.utils.lucene import EnhanceLuceneAdapter

SYNTAX_TRANSFORM_MAPPINGS = {
    # 不转换
    "msg=success": "msg=success",
    'log: "lineno=1"': 'log: "lineno=1"',
    'lineno:"go to some"': 'lineno:"go to some"',
    'lineno:"go and some"': 'lineno:"go and some"',
    'lineno:"go or some"': 'lineno:"go or some"',
    'lineno:"go not some"': 'lineno:"go not some"',
    # 符号转换
    "lineno=1": "lineno: =1",
    'log : "lineno<125" AND lineno<126': 'log : "lineno<125" AND lineno: <126',
    'lineno>126 AND log : "lineno>125"': 'lineno: >126 AND log : "lineno>125"',
    'log : "lineno=125" AND lineno=126': 'log : "lineno=125" AND lineno: =126',
    # 大小写转换
    'lineno:[1 to 10]': 'lineno:[1 TO 10]',
    'lineno:[1 and 10]': 'lineno:[1 AND 10]',
    'lineno:[1 or 10]': 'lineno:[1 OR 10]',
    'lineno:"go to some" and lineno:[1 to 10]': 'lineno:"go to some" and lineno:[1 TO 10]',
}


class TestSyntaxTransform(unittest.TestCase):
    def setUp(self):
        self.adapter = EnhanceLuceneAdapter('')

    def test_symbols_transform(self):
        for k, v in SYNTAX_TRANSFORM_MAPPINGS.items():
            self.adapter.query_string = k
            data = self.adapter.enhance()
            self.assertEqual(data, v)
