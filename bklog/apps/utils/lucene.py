import copy
import re
from collections import Counter, deque
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from django.utils.translation import gettext_lazy as _
from luqum.auto_head_tail import auto_head_tail
from luqum.exceptions import IllegalCharacterError, ParseSyntaxError
from luqum.parser import lexer, parser
from luqum.utils import UnknownOperationResolver
from luqum.visitor import TreeTransformer

from apps.constants import (
    BRACKET_DICT,
    DEFAULT_FIELD_OPERATOR,
    FIELD_GROUP_OPERATOR,
    FULL_TEXT_SEARCH_FIELD_NAME,
    FULL_WIDTH_CHAR_MAP,
    FULL_WIDTH_COLON,
    HIGH_CHAR,
    LOW_CHAR,
    LUCENE_NUMERIC_OPERATORS,
    LUCENE_NUMERIC_TYPES,
    LUCENE_RESERVED_CHARS,
    MAX_RESOLVE_TIMES,
    PLUS_OPERATOR,
    PROHIBIT_OPERATOR,
    WORD_RANGE_OPERATORS,
    LuceneReservedLogicOperatorEnum,
    LuceneSyntaxEnum,
)
from apps.exceptions import UnknownLuceneOperatorException
from apps.log_databus.constants import TargetNodeTypeEnum
from apps.log_search.constants import DEFAULT_BK_CLOUD_ID, OperatorEnum
from apps.utils import ChoicesEnum
from apps.utils.log import logger


def get_node_lucene_syntax(node):
    """获取该节点lucene语法类型"""
    return node.__class__.__name__


@dataclass
class LuceneField(object):
    """Lucene解析出的Field类"""

    pos: int = 0
    # field为原始字段名, name为带重复次数的字段名
    field_name: str = ""
    name: str = ""
    # 此处type为Lucene语法的type
    type: str = ""
    operator: str = DEFAULT_FIELD_OPERATOR
    value: str = ""
    # 标识是否为全文检索字段
    is_full_text_field: bool = False
    # 标识同名字段出现的次数
    repeat_count: int = 0

    def __post_init__(self):
        self.field_name = self.name


class LuceneParser(object):
    """lucene语法的解析类"""

    def __init__(self, keyword: str) -> None:
        self.keyword = keyword
        self.lexer = lexer.clone()

    def parsing(self) -> List[LuceneField]:
        """解析lucene语法入口函数"""
        tree = parser.parse(self.keyword, lexer=self.lexer)
        fields = self._get_method(tree)
        if isinstance(fields, list):
            # 以下逻辑为同名字段增加额外标识符
            names = Counter([field.name for field in fields])
            if not names:
                return fields
            for name, cnt in names.items():
                if cnt > 1:
                    number = 1
                    for field in fields:
                        if field.name == name:
                            field.name = f"{name}({number})"
                            field.repeat_count = number
                            number += 1
            return fields

        return [fields]

    def _get_method(self, node):
        """获取解析方法"""
        node_type = get_node_lucene_syntax(node)
        method_name = "parsing_{}".format(node_type.lower())
        return getattr(self, method_name)(node)

    def parsing_word(self, node):
        """解析单词"""
        field = LuceneField(
            pos=node.pos,
            name=FULL_TEXT_SEARCH_FIELD_NAME,
            operator=DEFAULT_FIELD_OPERATOR,
            type=LuceneSyntaxEnum.WORD,
            value=node.value,
            is_full_text_field=True,
        )
        match = re.search(WORD_RANGE_OPERATORS, node.value)
        if match:
            operator = match.group(0)
            field.operator = operator
            field.value = node.value.split(operator)[-1]
        return field

    def parsing_phrase(self, node):
        """解析短语"""
        field = LuceneField(
            pos=node.pos,
            name=FULL_TEXT_SEARCH_FIELD_NAME,
            operator="=",
            type=LuceneSyntaxEnum.PHRASE,
            value=node.value,
            is_full_text_field=True,
        )
        return field

    def parsing_searchfield(self, node):
        """解析搜索字段"""
        field = LuceneField(pos=node.pos, name=node.name, type=LuceneSyntaxEnum.SEARCH_FIELD)
        new_field = self._get_method(node.expr)
        field.type = new_field.type
        field.operator = new_field.operator
        field.value = new_field.value
        return field

    def parsing_fieldgroup(self, node):
        """解析字段组"""
        field = LuceneField(
            pos=node.pos,
            type=LuceneSyntaxEnum.FIELD_GROUP,
            operator=FIELD_GROUP_OPERATOR,
            value="({})".format(str(node.expr)),
        )
        return field

    def parsing_group(self, node):
        """ """
        fields = []
        for children in node.children:
            children_fields = self._get_method(children)
            if isinstance(children_fields, list):
                fields.extend(children_fields)
            else:
                fields.append(children_fields)
        return fields

    def parsing_range(self, node):
        """ """
        field = LuceneField(pos=node.pos, type=LuceneSyntaxEnum.RANGE, value=str(node))
        field.operator = "{}{}".format(LOW_CHAR[node.include_low], HIGH_CHAR[node.include_high])
        return field

    def parsing_fuzzy(self, node):
        """ """
        field = LuceneField(pos=node.pos, operator=DEFAULT_FIELD_OPERATOR, type=LuceneSyntaxEnum.FUZZY, value=str(node))
        return field

    def parsing_regex(self, node):
        """ """
        field = LuceneField(pos=node.pos, operator=DEFAULT_FIELD_OPERATOR, type=LuceneSyntaxEnum.REGEX, value=str(node))
        return field

    def parsing_proximity(self, node):
        """ """
        field = LuceneField(
            pos=node.pos,
            name=FULL_TEXT_SEARCH_FIELD_NAME,
            operator=DEFAULT_FIELD_OPERATOR,
            type=LuceneSyntaxEnum.PROXIMITY,
            value=str(node),
            is_full_text_field=True,
        )
        return field

    def parsing_oroperation(self, node):
        """解析或操作"""
        fields = []
        for operand in node.operands:
            operand_fields = self._get_method(operand)
            if isinstance(operand_fields, list):
                fields.extend(operand_fields)
            else:
                fields.append(operand_fields)
        return fields

    def parsing_andoperation(self, node):
        """ """
        fields = []
        for operand in node.operands:
            operand_fields = self._get_method(operand)
            if isinstance(operand_fields, list):
                fields.extend(operand_fields)
            else:
                fields.append(operand_fields)
        return fields

    def parsing_not(self, node):
        """ """
        field = LuceneField(
            pos=node.pos,
            name=FULL_TEXT_SEARCH_FIELD_NAME,
            operator=LuceneReservedLogicOperatorEnum.NOT.value,
            type=LuceneSyntaxEnum.NOT,
            value=self._get_method(node.a).value,
            is_full_text_field=True,
        )
        return field

    def parsing_plus(self, node):
        """ """
        field = LuceneField(
            pos=node.pos,
            name=FULL_TEXT_SEARCH_FIELD_NAME,
            operator=PLUS_OPERATOR,
            type=LuceneSyntaxEnum.PLUS,
            value=self._get_method(node.a).value,
            is_full_text_field=True,
        )
        return field

    def parsing_prohibit(self, node):
        """解析减号"""
        field = LuceneField(
            pos=node.pos,
            name=FULL_TEXT_SEARCH_FIELD_NAME,
            operator=PROHIBIT_OPERATOR,
            type=LuceneSyntaxEnum.PROHIBIT,
            value=self._get_method(node.a).value,
            is_full_text_field=True,
        )
        return field

    def parsing_unknownoperation(self, node):
        """解析未知操作"""
        raise UnknownLuceneOperatorException()


class LuceneTransformer(TreeTransformer):
    """Lucene语句转换器"""

    def __init__(self, track_new_parents=False, **kwargs):
        self.lexer = lexer.clone()
        super().__init__(track_new_parents, **kwargs)

    def visit_search_field(self, node, context):
        """SEARCH_FIELD 类型转换"""
        if node.pos == context["pos"]:
            name, value = node.name, context["value"]
            if get_node_lucene_syntax(node.expr) == LuceneSyntaxEnum.WORD:
                operator = LuceneParser(keyword=str(node)).parsing()[0].operator
                if operator in WORD_RANGE_OPERATORS:
                    node = parser.parse(f"{name}: {operator}{value}", lexer=self.lexer)
                else:
                    node = parser.parse(f"{name}: {value}", lexer=self.lexer)
            else:
                node = parser.parse(f"{name}: {value}", lexer=self.lexer)

        yield from self.generic_visit(node, context)

    def visit_word(self, node, context):
        """WORD 类型转换"""
        if node.pos == context["pos"]:
            node.value = str(context["value"])
        yield from self.generic_visit(node, context)

    def transform(self, keyword: str, params: list) -> str:
        """转换Lucene语句"""
        query_tree = parser.parse(keyword, lexer=self.lexer)
        for param in params:
            query_tree = self.visit(query_tree, param)
        return re.sub(r'\s{2,}', ' ', str(auto_head_tail(query_tree)))


@dataclass
class InspectResult(object):
    is_legal: bool = True
    message: str = ""


class BaseInspector(object):
    """检查器基类"""

    syntax_error_message = ""

    def __init__(self, keyword: str):
        self.keyword = keyword
        self.result = InspectResult()
        self.lexer = lexer.clone()

    def get_result(self):
        return self.result

    def set_illegal(self):
        """设置检查结果为非法"""
        self.result.is_legal = False
        self.result.message = self.syntax_error_message

    def inspect(self):
        """检查"""
        raise NotImplementedError

    def remove_unexpected_character(self, match):
        """根据RE match来移除异常字符"""
        unexpect_word_len = len(match[1])
        position = int(str(match[2]))
        # "127.0.0.1 这种单个引号在开头的情况，需要移除引号
        if match[1].startswith('"') and not match[1].endswith('"'):
            self.keyword = self.keyword[:position] + self.keyword[position + 1 :]
            return
        if match[1].startswith("'") and not match[1].endswith("'"):
            self.keyword = self.keyword[:position] + self.keyword[position + 1 :]
            return
        self.keyword = self.keyword[:position] + self.keyword[position + unexpect_word_len :]
        self.keyword = self.keyword.strip()

    def replace_unexpected_character(self, pos: int, char: str):
        """替换字符"""
        if pos <= 0:
            self.keyword = char + self.keyword[1:]
        elif pos >= len(self.keyword) - 1:
            self.keyword = self.keyword[:-1] + char
        else:
            self.keyword = self.keyword[:pos] + char + self.keyword[pos + 1 :]


class ChinesePunctuationInspector(BaseInspector):
    """中文引号转换"""

    syntax_error_message = _("中文标点异常")

    chinese_punctuation_re = r"(“.*?”)"

    def inspect(self):
        p = re.compile(self.chinese_punctuation_re)
        match_groups = [m for m in p.finditer(self.keyword)]
        if not match_groups:
            return
        for m in p.finditer(self.keyword):
            self.replace_unexpected_character(m.start(), '"')
            self.replace_unexpected_character(m.end(), '"')
        self.set_illegal()


class IllegalCharacterInspector(BaseInspector):
    """非法字符检查"""

    syntax_error_message = _("异常字符")

    # 非法字符正则
    illegal_character_re = r"Illegal character '(.*)' at position (\d+)"
    # 非预期字符正则
    unexpect_word_re = r"Syntax error in input : unexpected  '(.*)' at position (\d+)"

    def inspect(self):
        try:
            parser.parse(self.keyword, lexer=self.lexer)
        except IllegalCharacterError as e:
            match = re.search(self.illegal_character_re, str(e))
            if match:
                self.remove_unexpected_character(match)
                self.set_illegal()
        except ParseSyntaxError as e:
            match = re.search(self.unexpect_word_re, str(e))
            if match:
                self.remove_unexpected_character(match)
                self.set_illegal()
        except Exception:  # pylint: disable=broad-except
            return


class IllegalRangeSyntaxInspector(BaseInspector):
    """非法RANGE语法检查"""

    syntax_error_message = _("非法RANGE语法")

    # RANGE语法正则
    range_re = r":[\s]?[\[]?.*?(?i:TO).*"

    def inspect(self):
        try:
            parser.parse(self.keyword, lexer=self.lexer)
        except Exception:  # pylint: disable=broad-except
            new_keyword = self.keyword
            for i in self.keyword.split("AND"):
                for keyword_slice in i.split("OR"):
                    match = re.search(self.range_re, keyword_slice)
                    if not match:
                        continue
                    match_range_str = match.string.split(":")[-1].strip()
                    new_match_range_str = match_range_str
                    if not new_match_range_str.startswith("["):
                        new_match_range_str = "[" + new_match_range_str
                    if not new_match_range_str.endswith("]"):
                        new_match_range_str = new_match_range_str + "]"
                    start, end = new_match_range_str.lower()[1:-1].split("to")
                    start = start.strip()
                    end = end.strip()
                    if not start:
                        start = "*"
                    if not end:
                        end = "*"
                    new_range_str = f"[{start} TO {end}]"
                    new_keyword = new_keyword.replace(match_range_str, new_range_str).strip()

            if self.keyword != new_keyword:
                self.set_illegal()
            self.keyword = new_keyword


class IllegalBracketInspector(BaseInspector):
    """修复括号不匹配"""

    syntax_error_message = _("括号不匹配")
    # 非预期语法re
    unexpect_unmatched_re = (
        "Syntax error in input : unexpected end of expression (maybe due to unmatched parenthesis) at the end!"
    )

    def inspect(self):
        try:
            parser.parse(self.keyword, lexer=self.lexer)
        except ParseSyntaxError as e:
            if str(e) == self.unexpect_unmatched_re:
                s = deque()
                for index in range(len(self.keyword)):
                    symbol = self.keyword[index]
                    # 左括号入栈
                    if symbol in BRACKET_DICT.keys():
                        s.append({"symbol": symbol, "index": index})
                        continue
                    if symbol in BRACKET_DICT.values():
                        if s and symbol == BRACKET_DICT.get(s[-1]["symbol"], ""):
                            # 右括号出栈
                            s.pop()
                            continue
                        s.append({"symbol": symbol, "index": index})
                        # 如果栈首尾匹配, 则异常的括号是栈顶向下第二个
                        if s[-1]["symbol"] == BRACKET_DICT.get(s[0]["symbol"], ""):
                            self.keyword = self.keyword[: s[-2]["index"]] + self.keyword[s[-2]["index"] + 1 :]
                        # 否则异常的括号是栈顶元素
                        else:
                            self.keyword = self.keyword[: s[-1]["index"]] + self.keyword[s[-1]["index"] + 1 :]
                        self.set_illegal()
                        return
                if not s:
                    return
                self.keyword = self.keyword[: s[-1]["index"]] + self.keyword[s[-1]["index"] + 1 :].strip()
                self.set_illegal()
        except Exception:  # pylint: disable=broad-except
            return


class IllegalColonInspector(BaseInspector):
    """修复冒号不匹配"""

    syntax_error_message = _("多余的冒号")
    # 非预期语法re
    unexpect_unmatched_re = (
        "Syntax error in input : unexpected end of expression (maybe due to unmatched parenthesis) at the end!"
    )

    def inspect(self):
        try:
            parser.parse(self.keyword, lexer=self.lexer)
        except ParseSyntaxError as e:
            if str(e) == self.unexpect_unmatched_re:
                if self.keyword.find(":") == len(self.keyword) - 1:
                    self.keyword = self.keyword[:-1].strip()
                    self.set_illegal()
        except Exception:  # pylint: disable=broad-except
            return


class IllegalOperatorInspector(BaseInspector):
    """修复非法运算符"""

    syntax_error_message = _("非法逻辑运算符(AND, OR, NOT)")
    unexpect_operators = ["AND", "OR", "NOT"]
    # 非预期语法re
    unexpect_unmatched_re = (
        "Syntax error in input : unexpected end of expression (maybe due to unmatched parenthesis) at the end!"
    )

    def inspect(self):
        try:
            parser.parse(self.keyword, lexer=self.lexer)
        except ParseSyntaxError as e:
            if str(e) != self.unexpect_unmatched_re:
                return
            for operator in self.unexpect_operators:
                if operator not in self.keyword:
                    continue
                _operator_pos = self.keyword.find(operator)
                if _operator_pos == len(self.keyword) - len(operator):
                    self.keyword = self.keyword[:_operator_pos].strip()
                    self.set_illegal()
                    # 单次修复
                    break
        except Exception:  # pylint: disable=broad-except
            return


class UnknownOperatorInspector(BaseInspector):
    """修复未知运算符"""

    syntax_error_message = _("未知操作符")

    def inspect(self):
        try:
            parser.parse(self.keyword, lexer=self.lexer)
        except UnknownLuceneOperatorException:
            resolver = UnknownOperationResolver()
            self.keyword = str(resolver(parser.parse(self.keyword, lexer=self.lexer)))
            self.set_illegal()
        except Exception:  # pylint: disable=broad-except
            return


class DefaultInspector(BaseInspector):
    """默认检查器, 用于最后检查语法错误是否被修复"""

    syntax_error_message = _("未知异常")

    def inspect(self):
        try:
            parser.parse(self.keyword, lexer=self.lexer)
            LuceneParser(keyword=self.keyword).parsing()
        # "aaa bbb ccc"语法在parser.parse阶段不会解析报错
        # 但是在LuceneParser中会走到parsing_unknownoperation, 人为raise UnknownLuceneOperatorException
        except UnknownLuceneOperatorException:
            resolver = UnknownOperationResolver()
            self.keyword = str(resolver(parser.parse(self.keyword, lexer=self.lexer)))
            self.set_illegal()
        except Exception:  # pylint: disable=broad-except
            self.set_illegal()


class LuceneSyntaxResolver(object):
    """lucene语法检查以及修复器"""

    REGISTERED_INSPECTORS = [
        ChinesePunctuationInspector,
        # IllegalRangeInspector得放在前面是因为 RANGE 的语法会和 IllegalCharacterInspector 中的 TO 冲突
        IllegalRangeSyntaxInspector,
        IllegalCharacterInspector,
        IllegalColonInspector,
        IllegalBracketInspector,
        IllegalOperatorInspector,
        UnknownOperatorInspector,
        DefaultInspector,
    ]

    def __init__(self, keyword: str):
        self.keyword = keyword
        self.messages = []

    def inspect(self):
        messages = []
        for inspector_class in self.REGISTERED_INSPECTORS:
            inspector = inspector_class(self.keyword)
            inspector.inspect()
            self.keyword = inspector.keyword
            result = inspector.get_result()
            if not result.is_legal:
                messages.append(str(asdict(result)["message"]))
        if not messages:
            return True
        self.messages.extend(messages)

    def resolve(self):
        is_resolved = False
        for __ in range(MAX_RESOLVE_TIMES):
            if self.inspect():
                is_resolved = True
                break
        self.messages = set(self.messages)
        if is_resolved and str(DefaultInspector.syntax_error_message) in self.messages:
            self.messages.remove(str(DefaultInspector.syntax_error_message))
        return {
            "is_legal": False if self.messages else True,
            "is_resolved": is_resolved,
            "message": "\n".join(self.messages),
            "keyword": self.keyword,
        }


def generate_query_string(params: dict) -> str:
    """生成查询字符串"""
    key_word = params.get("keyword", "")
    if key_word is None:
        key_word = ""
    query_string = key_word
    # 保留host_scopes相关逻辑是为了兼容旧版本
    host_scopes = params.get("host_scopes", {})
    target_nodes = host_scopes.get("target_nodes", [])

    if target_nodes:
        if host_scopes["target_node_type"] == TargetNodeTypeEnum.INSTANCE.value:
            query_string += " AND ({})".format(
                ",".join([f"{target_node['bk_cloud_id']}:{target_node['ip']}" for target_node in target_nodes])
            )
        elif host_scopes["target_node_type"] == TargetNodeTypeEnum.DYNAMIC_GROUP.value:
            dynamic_name_list = [str(target_node["name"]) for target_node in target_nodes]
            query_string += " AND (dynamic_group_name:" + ",".join(dynamic_name_list) + ")"
        else:
            first_node, *_ = target_nodes
            target_list = [str(target_node["bk_inst_id"]) for target_node in target_nodes]
            query_string += f" AND ({first_node['bk_obj_id']}:" + ",".join(target_list) + ")"

    if host_scopes.get("modules"):
        modules_list = [str(_module["bk_inst_id"]) for _module in host_scopes["modules"]]
        query_string += " AND (modules:" + ",".join(modules_list) + ")"
        host_scopes["target_node_type"] = TargetNodeTypeEnum.TOPO.value
        host_scopes["target_nodes"] = host_scopes["modules"]

    if host_scopes.get("ips"):
        query_string += " AND (ips:" + host_scopes["ips"] + ")"
        host_scopes["target_node_type"] = TargetNodeTypeEnum.INSTANCE.value
        host_scopes["target_nodes"] = [
            {"ip": ip, "bk_cloud_id": DEFAULT_BK_CLOUD_ID} for ip in host_scopes["ips"].split(",")
        ]

    ipchooser = params.get("ip_chooser", {})
    for node_type, node_value in ipchooser.items():
        if node_type == "host_list":
            _host_slice = []
            _host_id_slice = []
            for _node in node_value:
                if _node.get("id"):
                    _host_id_slice.append(str(_node["id"]))
                    continue
                # 这里key值是参考了format_hosts方法的返回值
                _host_slice.append(f"{_node.get('cloud_area', {}).get('id', 0)}:{_node['ip']}")
            # 分开以便于前端展示
            query_string += " AND (host_id: " + ",".join(_host_id_slice) + " AND (host: " + ",".join(_host_slice) + ")"
        elif node_type == "node_list":
            for _node in node_value:
                query_string += " AND ({}: {})".format(_node["object_id"], _node["instance_id"])
        else:
            node_type_name = node_type.split("_list")[0].lower()
            query_string += " AND ({}: {})".format(node_type_name, ",".join([str(i["id"]) for i in node_value]))

    additions = params.get("addition", [])
    if additions:
        str_additions = []
        for addition in additions:
            if addition["operator"] in [OperatorEnum.IS_TRUE["operator"], OperatorEnum.IS_FALSE["operator"]]:
                str_additions.append(f'{addition["field"]} {addition["operator"]}')
            else:
                str_additions.append(f'{addition["field"]} {addition["operator"]} {addition.get("value", "")}')

        query_string += " AND (" + " AND ".join(str_additions) + ")"
    return query_string


class EnhanceLuceneBase(object):
    """
    增强Lucene语法
    """

    RE = ""

    def __init__(self, query_string: str = ""):
        self.query_string = query_string

    def match(self) -> bool:
        raise NotImplementedError

    def transform(self) -> str:
        raise NotImplementedError


class CaseInsensitiveLogicalEnhanceLucene(EnhanceLuceneBase):
    """
    不区分大小写的逻辑运算符
    例如: A and B => A AND B
    """

    RE_STRING = r'(".*?")|(/.*?/)'
    RE = r'\b(and|or|not|to)\b'

    def __init__(self, query_string: str = ""):
        super().__init__(query_string)

    def match(self) -> bool:
        # 替换字符串,避免干扰判断
        check_query_string = re.sub(self.RE_STRING, "x", self.query_string, flags=re.DOTALL)
        pattern = re.compile(self.RE)
        split_strings = re.split(r'(:\s*\S+\s*)', check_query_string)
        for part in split_strings:
            if ':' not in part and pattern.search(part):
                return True
        return False

    def transform(self) -> str:
        if not self.match():
            return self.query_string
        pattern = re.compile(self.RE)
        pattern1 = re.compile(r'(:\s*\S+\s*)')
        pattern2 = re.compile(r':\s*(and|or|not|to)')
        split_strings = re.split(self.RE_STRING, self.query_string, flags=re.DOTALL)
        # 调整列表，删除None值（由正则表达式分割位置的特殊性产生）
        split_strings = [s for s in split_strings if s is not None]
        for i, part in enumerate(split_strings):
            if not (part.startswith('"') and part.endswith('"')) and not (part.startswith('/') and part.endswith('/')):
                match = pattern2.search(part)
                # 处理log: and的情况,and不应该被转换
                if match:
                    part_strings = pattern1.split(part)
                    for j, child_part in enumerate(part_strings):
                        if not child_part.startswith(":"):
                            part_strings[j] = pattern.sub(lambda m: m.group().upper(), child_part)
                    split_strings[i] = ''.join(part_strings)
                else:
                    split_strings[i] = pattern.sub(lambda m: m.group().upper(), part)
        return ''.join(split_strings)


class OperatorEnhanceEnum(ChoicesEnum):
    """
    增强运算符枚举
    """

    LE = "<="
    LT = "<"
    GE = ">="
    GT = ">"


class OperatorEnhanceLucene(EnhanceLuceneBase):
    """
    兼容用户增强运算符
    例如: A > 3 => A: >3
    """

    RE_STRING = r'(".*?")|(/.*?/)'
    # 匹配不是以引号、字母（大小写）、数字或下划线开头和结尾的字符串;确保"lineno=125"这样的字符串不会被匹配或被匹配成ineno=125
    RE = r'(?<!["a-zA-Z0-9_])([a-zA-Z0-9_]+)\s*(>=|<=|>|<|=|!=)\s*([\d.]+)(?!["a-zA-Z0-9_])'
    ENHANCE_OPERATORS = [
        OperatorEnhanceEnum.LT.value,
        OperatorEnhanceEnum.LE.value,
        OperatorEnhanceEnum.GT.value,
        OperatorEnhanceEnum.GE.value,
    ]

    def __init__(self, query_string: str):
        super().__init__(query_string)

    def match(self):
        # 替换字符串,避免干扰判断
        check_query_string = re.sub(self.RE_STRING, "x", self.query_string, flags=re.DOTALL)
        if re.search(self.RE, check_query_string):
            return True
        return False

    def transform(self) -> str:
        if not self.match():
            return self.query_string
        query_string_list = re.split(self.RE_STRING, self.query_string, flags=re.DOTALL)
        # 调整列表，删除None值（由正则表达式分割位置的特殊性产生）
        query_string_list = [s for s in query_string_list if s is not None]
        result_string = ""
        match_pattern = re.compile(self.RE_STRING, flags=re.DOTALL)
        sub_pattern = re.compile(self.RE)
        for _query_string in query_string_list:
            if match_pattern.match(_query_string):
                result_string += _query_string
            else:
                result_string += sub_pattern.sub(r'\1: \2\3', _query_string)
        return result_string


class ReservedLogicalEnhanceLucene(EnhanceLuceneBase):
    """
    将内置的逻辑运算符转换为带引号的形式, 兼容用户真的想查询这些词的情况
    例如: A: AND => A: "AND"
    """

    RE_STRING = r'(".*?")|(/.*?/)'
    RE = r'(?<![a-zA-Z0-9_])(and|or|not|AND|OR|NOT)(?![a-zA-Z0-9_])'

    def match(self):
        query_string = copy.deepcopy(self.query_string)
        # 替换字符串,避免干扰判断
        filter_matches = list(re.finditer(self.RE_STRING, query_string, flags=re.DOTALL))
        for match in filter_matches:
            start, end = match.span()
            query_string = query_string[:start] + (end - start) * "x" + query_string[end:]
        matches = list(re.finditer(self.RE, query_string))
        if matches:
            for match in matches:
                start, __ = match.span()
                # 检查逻辑运算符前面是否有冒号
                colon_index = self.query_string.rfind(':', 0, start)
                if colon_index != -1:
                    # 如果找到冒号，检查冒号后面是否有空白字符和逻辑运算符
                    post_colon = self.query_string[colon_index + 1 : start].strip()
                    if post_colon == "":
                        return True
        return False

    def transform(self) -> str:
        if not self.match():
            return self.query_string
        query_string = copy.deepcopy(self.query_string)
        # 替换不希望被正则匹配的数据,并记录下位置信息
        filter_matches = list(re.finditer(self.RE_STRING, query_string, flags=re.DOTALL))
        filter_list = []
        for match in filter_matches:
            start, end = match.span()
            filter_string = query_string[start:end]
            query_string = query_string[:start] + (end - start) * "x" + query_string[end:]
            filter_list.append(
                {
                    "start": start,
                    "end": end,
                    "filter_string": filter_string,
                }
            )

        records = []
        matches = list(re.finditer(self.RE, self.query_string))
        offset = 0
        for match in matches:
            start, end = match.span()
            operator = match.group()

            # 检查逻辑运算符前面是否有冒号
            colon_index = query_string.rfind(':', 0, start + offset)
            if colon_index != -1:
                # 如果找到冒号，检查冒号后面是否有空白字符和逻辑运算符
                post_colon = query_string[colon_index + 1 : start + offset].strip()
                if post_colon == "":
                    # 记录下需要替换的位置
                    records.append({"start": start, "end": end, "operator": operator})

        # 还原上面替换的字符串
        for item in filter_list:
            query_string = query_string[: item["start"]] + item["filter_string"] + query_string[item["end"] :]

        # 将逻辑运算符替换为带引号的形式，保留原始大小写
        for item in records:
            query_string = (
                query_string[: item["start"] + offset] + f'"{item["operator"]}"' + query_string[item["end"] + offset :]
            )
            offset += 2
        return query_string


class EnhanceLuceneAdapter(object):
    """
    增强Lucene语法适配器
    依次检查是否满足需要兼容的语法类型, 并转换成lucene支持的语法
    REGISTERED_ENHANCERS中的顺序决定了检查的顺序
    """

    REGISTERED_ENHANCERS = EnhanceLuceneBase.__subclasses__()

    def __init__(self, query_string: str):
        # 原始的query_string, 用于日志记录, 前端回显
        self.origin_query_string: str = query_string
        # 增强后的query_string
        self.query_string: str = query_string
        self.is_enhanced: bool = False

    def enhance(self) -> str:
        for enhancer_class in self.REGISTERED_ENHANCERS:
            enhancer = enhancer_class(self.query_string)
            if enhancer.match():
                self.is_enhanced = True
                self.query_string = enhancer.transform()
        if self.is_enhanced:
            logger.info(f"Enhanced lucene query string from [{self.origin_query_string}] to [{self.query_string}]")
        return self.query_string


@dataclass
class LuceneCheckResult:
    """
    Lucene语法检查结果
    """

    # 是否检查
    checked: bool = False
    # 是否合法
    legal: bool = True
    # 是否可以修复
    fixable: bool = True
    # 是否修复
    fixed: bool = False
    # 错误信息
    error: str = ""
    # 修复建议
    suggestion: str = _("你可能想输入: ")
    # 修复后的query_string
    fixed_query_string: str = ""


class LuceneCheckerBase(object):
    """
    Lucene语法检查器基类
    """

    # prompt message
    prompt_template = _("{error}, {suggestion}")

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None, force_check: bool = False):
        """
        初始化
        :param query_string: 查询字符串
        :param fields: 字段列表
        :param force_check: 是否强制检查, 强制检查即LuceneParser解析成功时候也检查
        """
        self.query_string = query_string
        self.force_check = force_check
        self.fields = fields or []
        self.check_result = LuceneCheckResult(fixed_query_string=query_string)
        # 子查询列表
        self.sub_query_list: List[str] = []
        self.field_name_list: List[str] = []
        # 分词字段列表
        self.analyzed_field_list: List[str] = []
        # 数值字段列表
        self.numeric_field_list: List[str] = []
        # LuceneParser解析后的字段列表
        self.parsed_fields: List[LuceneField] = []
        self.prepare()

    def prepare(self):
        """
        准备工作, 将query_string分割成子查询, 以便于后续检查
        如果后续要在prepare里面做一些额外的工作, 需要在子类中重写这个方法, 最后返回super().prepare()即可
        """
        # 构造模式字符串，其中的(?:...)用于标记一个子表达式开始和结束的位置，匹配满足这个子表达式规则的字符串
        pattern = '|'.join(r'\b{}\b'.format(x) for x in LuceneReservedLogicOperatorEnum.get_keys())
        # 使用正则来分割字符串，但是保持分割引号的存在
        result = re.split('(' + pattern + ')', self.query_string)
        # 去除结果中的空格部分，这样就不会有头尾空格了
        self.sub_query_list = [x.strip() for x in result if x.strip() != ""]
        if not self.fields:
            return
        for field in self.fields:
            field_name = field.get("field_name")
            if field.get("is_analyzed"):
                self.analyzed_field_list.append(field_name)
            if field.get("field_type") in LUCENE_NUMERIC_TYPES:
                self.numeric_field_list.append(field_name)
            self.field_name_list.append(field_name)

    def check(self):
        """
        检查语法是否正确, 如果不正确, 则设置error
        """
        self.check_result.checked = True
        try:
            self.parsed_fields = LuceneParser(keyword=self.query_string).parsing()
            if not self.force_check:
                self.check_result.legal = True
                return
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            self.check_result.legal = self._check()
        except Exception as e:  # pylint: disable=broad-except
            self.check_result.fixable = False
            self.check_result.legal = False
            self.check_result.error = _("语法错误")
            logger.error(f"lucene check unexpected error: {e}")
            return

    def _check(self):
        """
        检查语法是否正确, 实际需要实现的方法
        如果不正确, 则设置 legal=False 以及 error
        """
        raise NotImplementedError

    def prompt(self):
        """
        返回提示信息, 如果没有错误, 则返回空字符串, 否则返回错误信息
        """
        if not self.check_result.checked:
            self.check()
        if self.check_result.legal or not self.check_result.error:
            return ""
        if self.check_result.error and self.check_result.fixable and not self.check_result.fixed:
            self.fix()
        if self.check_result.fixable:
            return self.prompt_template.format(
                error=self.check_result.error,
                suggestion=self.check_result.suggestion + self.check_result.fixed_query_string,
            )
        return self.prompt_template.format(error=self.check_result.error, suggestion=self.check_result.suggestion)

    def fix(self):
        """
        修复语法错误, 如果修复成功, 则设置is_fixed为True, 将修复后的query_string赋值给fixed_query_string
        """
        self.check_result.fixed_query_string = self._fix()
        self.check_result.fixed = True

    def _fix(self) -> str:
        """
        修复语法错误, 实际需要实现的方法
        返回修复后的query_string
        """
        return self.query_string


class LuceneParenthesesChecker(LuceneCheckerBase):
    """
    括号配对检查器
    """

    PAIR_LEFT = '('
    PAIR_RIGHT = ')'

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields)
        # 检查是否多了左括号或者右括号, 如果多了, 则为True, 否则为False
        self.more_or_less: Optional[bool] = None

    def _fix(self):
        stack = deque()
        query_string = copy.deepcopy(self.query_string)
        for i, char in enumerate(query_string):
            if char == self.PAIR_LEFT:
                stack.append((char, i))
            elif char == self.PAIR_RIGHT:
                if not stack:
                    query_string = query_string[:i] + query_string[i + 1 :]
                else:
                    top_char, __ = stack.pop()
                    if not self.is_matching(top_char, char):
                        query_string = query_string[:i] + self.PAIR_LEFT + query_string[i:]

        while stack:
            stack.pop()
            query_string += self.PAIR_RIGHT
        return query_string

    def _check(self):
        stack = deque()
        for char in self.query_string:
            if char == self.PAIR_LEFT:
                stack.append(char)
            elif char == self.PAIR_RIGHT:
                if not stack:
                    self.more_or_less = True
                    self.check_result.error = _("多了 {pair}").format(pair=self.PAIR_RIGHT)
                    return False
                top_char = stack.pop()
                if not self.is_matching(top_char, char):
                    self.more_or_less = False
                    self.check_result.error = _("缺少 {pair}").format(pair=self.PAIR_LEFT)
                    return False
        if stack:
            self.more_or_less = False
            self.check_result.error = _("缺少 {pair}").format(pair=self.PAIR_RIGHT)
            return False
        return True

    def is_matching(self, left_char, right_char):
        return left_char == self.PAIR_LEFT and right_char == self.PAIR_RIGHT


class LuceneQuotesChecker(LuceneCheckerBase):
    """
    处理查询字符串中的引号使用情况的修正类
    """

    SINGLE_QUOTE = "'"
    DOUBLE_QUOTE = '"'
    CHARACTER_WHITESPACE = " "

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields, force_check=True)

    @staticmethod
    def check_quotes(s: str) -> bool:
        """
        检查字符串中的引号是否匹配, 要么左右都有, 要么左右都没有
        :param s: 字符串
        :return: 是否匹配
        """
        # 避免value是 YY-MM-DD HH:mm:SS 这种情况;避免包含冒号的字符串被分隔
        if (
            ":" in s
            and s.count(":") == 1
            and not (s.startswith("'") and s.endswith("'"))
            and not (s.startswith('"') and s.endswith('"'))
        ):
            __, s = s.split(":")

        left_single_quote = s.startswith("'")
        left_double_quote = s.startswith('"')
        right_single_quote = s.endswith("'")
        right_double_quote = s.endswith('"')

        if (
            (left_single_quote and right_single_quote)
            or (left_double_quote and right_double_quote)
            or (not left_single_quote and not left_double_quote and not right_single_quote and not right_double_quote)
        ):
            return True
        else:
            return False

    def _fix(self):
        words = []
        for word in self.query_string.split(self.CHARACTER_WHITESPACE):
            if word.startswith("(") or word.endswith(")"):
                words.append(word)
                continue
            if ":" in word:
                word_prefix, word = word.split(":")
                word_prefix += ":"
            else:
                word_prefix = ""
            if (
                # 先判断 ' 和 " 是否同时出现
                word.startswith(self.SINGLE_QUOTE)
                and word.endswith(self.DOUBLE_QUOTE)
                or word.startswith(self.DOUBLE_QUOTE)
                and word.endswith(self.SINGLE_QUOTE)
            ):
                word = self.DOUBLE_QUOTE + word[1:-1] + self.DOUBLE_QUOTE
            elif word.startswith(self.SINGLE_QUOTE) and not word.endswith(self.SINGLE_QUOTE):
                word = word + self.SINGLE_QUOTE
            elif word.startswith(self.DOUBLE_QUOTE) and not word.endswith(self.DOUBLE_QUOTE):
                word = word + self.DOUBLE_QUOTE
            elif word.endswith(self.SINGLE_QUOTE) and not word.startswith(self.SINGLE_QUOTE):
                word = self.SINGLE_QUOTE + word
            elif word.endswith(self.DOUBLE_QUOTE) and not word.startswith(self.DOUBLE_QUOTE):
                word = self.DOUBLE_QUOTE + word
            word = word_prefix + word
            words.append(word)

        return self.CHARACTER_WHITESPACE.join(words)

    def _check(self):
        try:
            fields = LuceneParser(keyword=self.query_string).parsing()
            for field in fields:
                if self.check_quotes(field.value):
                    continue
                self.check_result.error = _("引号不匹配")
                return False
        except Exception:  # pylint: disable=broad-except
            for sub_query in self.sub_query_list:
                if ':' not in sub_query:
                    continue
                __, field_expr = sub_query.split(':')
                field_expr = field_expr.strip()
                # 如果是空格分割的单词, 则每个单词都检查一遍
                if " " in field_expr:
                    for word in field_expr.split(" "):
                        if word and not self.check_quotes(word):
                            self.check_result.error = _("引号不匹配")
                            return False
                else:
                    if field_expr and not self.check_quotes(field_expr):
                        self.check_result.error = _("引号不匹配")
                        return False
        return True


class LuceneRangeChecker(LuceneCheckerBase):
    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields)

    @staticmethod
    def remove_left_consecutive_brackets(s: str):
        matches = re.findall(r'\[+\{+|\{+\[+|\[+|\{+', s)
        max_match = max(matches, key=len) if matches else None
        if not max_match:
            return s
        return s.replace(max_match, max_match[-1])

    @staticmethod
    def remove_right_consecutive_brackets(s: str):
        matches = re.findall(r'\]+\}+|\}+\]+|\]+|\}+', s)
        max_match = max(matches, key=len) if matches else None
        if not max_match:
            return s
        return s.replace(max_match, max_match[0])

    def _check(self):
        """
        在最小化子语句中按TO拆分, 检查左边和右边是否缺失边界以及边界符号
        """
        for sub_query in self.sub_query_list:
            if 'to' in sub_query:
                self.check_result.error = _("RANGE语法异常, to大小写需转换")
                return False
            if 'TO' in sub_query:
                parts = sub_query.split('TO')
                if len(parts) >= 2 and ":" not in parts[0]:
                    self.check_result.error = _("RANGE语法异常, 缺少字段名")
                    self.check_result.is_fixable = False
                    return False
                __, start = parts[0].split(':')
                start = start.strip()
                end = parts[1].strip()
                if not (re.match(r"^(?:\[\d+|\{\d+|\{\*)$", start) and re.match(r"^(?:\d+}|\d+]|.\*})$", end)):
                    self.check_result.error = _("RANGE语法异常, 格式错误")
                    return False

        return True

    def _fix_range(self, sub_query: str) -> str:
        def process_left_part(_left_part: str):
            _left_part = self.remove_left_consecutive_brackets(_left_part)
            field_name, upper_bound = _left_part.split(':')
            field_name = field_name.strip()
            upper_bound = upper_bound.strip()
            # 兼容 1 [ 这种情况
            if upper_bound and upper_bound[-1] in ('[', '{'):
                upper_bound = upper_bound[-1] + upper_bound[:-1].strip()
            if not upper_bound:
                upper_bound = '{*'
            else:
                if upper_bound[0] not in ('[', '{'):
                    if upper_bound[-1].isdigit():
                        upper_bound = '[' + upper_bound
                    else:
                        upper_bound = '{' + upper_bound
                if not upper_bound[-1].isdigit() and upper_bound[-1] != '*':
                    upper_bound += '*'
                if upper_bound == "[*":
                    upper_bound = "{*"
            return field_name, upper_bound

        def process_right_part(_right_part: str):
            _right_part = self.remove_right_consecutive_brackets(_right_part)
            # 兼容 [ 1 这种情况
            if _right_part and _right_part[0] in (']', '}'):
                _right_part = _right_part[1:].strip() + _right_part[0]
            if not _right_part:
                lower_bound = '*}'
            else:
                if _right_part[-1] not in (']', '}'):
                    if _right_part[0].isdigit():
                        lower_bound = _right_part + ']'
                    else:
                        lower_bound = _right_part + '}'
                else:
                    lower_bound = _right_part
                if not lower_bound[0].isdigit() and lower_bound[0] != '*':
                    lower_bound = '*' + lower_bound
            if lower_bound == "*]":
                lower_bound = "*}"
            return lower_bound

        left_part, right_part = sub_query.split('TO')
        left_result = process_left_part(left_part.strip())
        right_result = process_right_part(right_part.strip())
        return f"{left_result[0]}: {left_result[1]} TO {right_result}"

    def _fix(self):
        """
        按'TO'拆分, 依次修复左边和右边的边界和边界符号
        """
        fixed_sub_query_list = []
        for sub_query in self.sub_query_list:
            original_sub_query = copy.deepcopy(sub_query)
            if 'to' in sub_query:
                original_sub_query = sub_query.replace("to", "TO")

            if 'TO' in sub_query:
                fixed_sub_query_list.append(self._fix_range(sub_query))
            else:
                fixed_sub_query_list.append(original_sub_query)
        return ' '.join(fixed_sub_query_list)


class LuceneFieldExprChecker(LuceneCheckerBase):
    """
    检查字段查询内容是否存在, 该类的所有场景均无法修复, 即针对 "log: "这种场景
    """

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields)

    def _check(self):
        for sub_query in self.sub_query_list:
            if ':' not in sub_query:
                continue
            field_name, field_expr = sub_query.split(':')
            if "(" in field_name:
                field_name = field_name.split("(")[0]
            field_name = field_name.strip()
            field_expr = field_expr.strip()
            if not field_name:
                self.check_result.error = _("缺少字段").format(field_name=field_name)
                self.check_result.suggestion = _("请补充字段")
            elif not field_expr:
                self.check_result.error = _("字段{field_name}无查询内容").format(field_name=field_name)
                self.check_result.suggestion = _("请补齐查询内容").format(field_expr=field_expr)
            else:
                continue
            self.check_result.fixable = False
            return False
        return True


class LuceneFieldExistChecker(LuceneCheckerBase):
    """
    检查字段是否存在, 该类的所有场景均无法修复
    """

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields, force_check=True)

    def _check(self):
        try:
            fields = LuceneParser(keyword=self.query_string).parsing()
            for field in fields:
                if field.is_full_text_field:
                    continue
                if self.field_name_list and field.field_name not in self.field_name_list:
                    self.check_result.error = _("字段{field_name}不存在").format(field_name=field.field_name)
                    self.check_result.suggestion = _("请核对字段配置").format(field_name=field.field_name)
                    self.check_result.fixable = False
                    return False
        except Exception:  # pylint: disable=broad-except
            for sub_query in self.sub_query_list:
                if ':' not in sub_query:
                    continue
                field_name, field_expr = sub_query.split(':')
                if "(" in field_name:
                    field_name = field_name.split("(")[0]
                field_name = field_name.strip()
                if field_name and field_name not in self.field_name_list:
                    self.check_result.error = _("字段{field_name}不存在").format(field_name=field_name)
                    self.check_result.suggestion = _("请核对字段配置").format(field_name=field_name)
                    self.check_result.fixable = False
                    return False
        return True


class LuceneReservedCharChecker(LuceneCheckerBase):
    """
    检查是否有保留字符, 该类的所有场景均无法修复
    """

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        self.analyzed_field_list: List[str] = []
        super().__init__(query_string=query_string, fields=fields, force_check=True)

    def _check(self):
        try:
            fields = LuceneParser(keyword=self.query_string).parsing()
            for field in fields:
                if field.value in LUCENE_RESERVED_CHARS and field.field_name in self.analyzed_field_list:
                    self.check_result.error = _("该字段{field_name}已分词, 已自动忽略该符号'{field_expr}'").format(
                        field_name=field.field_name, field_expr=field.value
                    )
                    self.check_result.suggestion = _("""参考案例: content: "id=11" 和 content: id=11, 结果不同""")
                    self.check_result.fixable = False
                    return False
            return True
        except Exception:  # pylint: disable=broad-except
            for sub_query in self.sub_query_list:
                if ':' not in sub_query:
                    if sub_query.strip() in LUCENE_RESERVED_CHARS:
                        self.check_result.error = _("未检测到查询内容")
                        self.check_result.suggestion = _("请核对查询内容")
                        self.check_result.fixable = False
                        return False
                    continue
                field_name, field_expr = sub_query.split(':')
                field_name = field_name.strip()
                field_expr = field_expr.strip()
                if field_expr and field_expr in LUCENE_RESERVED_CHARS and field_name in self.analyzed_field_list:
                    self.check_result.error = _("该字段{field_name}已分词, 已自动忽略该符号'{field_expr}'").format(
                        field_name=field_name, field_expr=field_expr
                    )
                    self.check_result.suggestion = _("""参考案例: content: "id=11" 和 content: id=11, 结果不同""")
                else:
                    continue

                self.check_result.fixable = False
                return False
        return True


class LuceneFullWidthChecker(LuceneCheckerBase):
    """
    检查是否有全角字符
    """

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields, force_check=True)
        self.full_width_char_list: List[str] = []

    def extract_full_width_char(self, s: str):
        """提取全角字符"""
        for char in s:
            if char in FULL_WIDTH_CHAR_MAP and char not in self.full_width_char_list:
                self.full_width_char_list.append(char)

    @staticmethod
    def full_width_to_half_width(s: str) -> str:
        """全角转半角"""
        result = ''
        for char in s:
            if char in FULL_WIDTH_CHAR_MAP:
                char = FULL_WIDTH_CHAR_MAP[char]
            result += char
        return result

    def _check(self):
        try:
            fields = LuceneParser(keyword=self.query_string).parsing()
            for field in fields:
                if field.is_full_text_field:
                    continue
                self.extract_full_width_char(field.value)
        except Exception:  # pylint: disable=broad-except
            for sub_query in self.sub_query_list:
                if ':' not in sub_query:
                    continue
                field_name, field_expr = sub_query.split(':')
                if "(" in field_name:
                    field_name = field_name.split("(")[0]
                field_name = field_name.strip()
                field_expr = field_expr.strip()
                if field_name and field_name in self.analyzed_field_list:
                    self.extract_full_width_char(field_expr)
        finally:
            # 因为exception的情况下, k-v的切分是根据冒号, 所以可能会出现全角冒号的情况
            if FULL_WIDTH_COLON in self.query_string:
                self.full_width_char_list.append(FULL_WIDTH_COLON)
            if self.full_width_char_list:
                self.check_result.error = _("检测到使用了全角字符{char}").format(char=",".join(self.full_width_char_list))
                return False

        return True

    def _fix(self):
        return self.full_width_to_half_width(self.query_string)


class LuceneNumericOperatorChecker(LuceneCheckerBase):
    """
    检查数值类型的运算符, 数值类型只支持LUCENE_NUMERIC_OPERATORS内定义的, 该类的所有场景均无法修复
    """

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields, force_check=True)

    @staticmethod
    def _extract_illegal_numeric_operator(sub_query: str) -> Optional[str]:
        pattern = r'[<>=]+'
        matches = re.findall(pattern, sub_query)
        for match in matches:
            if match not in LUCENE_NUMERIC_OPERATORS:
                return match
        return None

    def _check(self):
        try:
            fields = LuceneParser(keyword=self.query_string).parsing()
            for field in fields:
                if field.is_full_text_field:
                    continue
                if field.field_name in self.numeric_field_list:
                    numeric_operator = self._extract_illegal_numeric_operator(field.value)
                    if numeric_operator:
                        self.check_result.error = _("该字段{field_name}为数值类型, 不支持运算符'{numeric_operator}'").format(
                            field_name=field.field_name, numeric_operator=numeric_operator
                        )
                        self.check_result.suggestion = _("请使用以下运算符: {numeric_operators}").format(
                            numeric_operators=",".join(LUCENE_NUMERIC_OPERATORS)
                        )
                        self.check_result.fixable = False
                        return False
        except Exception:  # pylint: disable=broad-except
            for sub_query in self.sub_query_list:
                if ':' not in sub_query:
                    continue
                field_name, field_expr = sub_query.split(':')
                if "(" in field_name:
                    field_name = field_name.split("(")[0]
                field_name = field_name.strip()
                field_expr = field_expr.strip()
                if field_name and field_name in self.numeric_field_list:
                    numeric_operator = self._extract_illegal_numeric_operator(field_expr)
                    if numeric_operator:
                        self.check_result.error = _("该字段{field_name}为数值类型, 不支持运算符'{numeric_operator}'").format(
                            field_name=field_name, numeric_operator=numeric_operator
                        )
                        self.check_result.suggestion = _("请使用以下运算符: {numeric_operators}").format(
                            numeric_operators=",".join(LUCENE_NUMERIC_OPERATORS)
                        )
                        self.check_result.fixable = False
                        return False

        return True


class LuceneNumericValueChecker(LuceneCheckerBase):
    """
    检查数值类型的值, 数值类型只支持整形和浮点数, 该类的所有场景均无法修复
    """

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields, force_check=True)

    @staticmethod
    def is_number(field_value: str):
        if field_value.strip() == "*":
            return True
        # force_check没办法知道sub_query的语法, 当值中存在RANGE语法的边界符时, 跳过检查
        for char in field_value:
            if char in ["[", "]", "{", "}"]:
                return True

        # 检查字符串是否为整数
        if field_value.isdigit():
            return True

        # 检查字符串是否为浮点数
        float_pattern = r'^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$'
        if re.match(float_pattern, field_value):
            return True

        return False

    def _check(self):
        try:
            fields = LuceneParser(keyword=self.query_string).parsing()
            for field in fields:
                if field.is_full_text_field:
                    continue
                if field.field_name in self.numeric_field_list:
                    if field.type in ["Word", "Phrase"] and not self.is_number(field.value):
                        self.check_result.error = _("该字段{field_name}为数值类型").format(field_name=field.field_name)
                        self.check_result.suggestion = _("请确认值的类型")
                        self.check_result.fixable = False
                        return False
        except Exception:  # pylint: disable=broad-except
            for sub_query in self.sub_query_list:
                if ':' not in sub_query:
                    continue
                field_name, field_expr = sub_query.split(':')
                if "(" in field_name:
                    field_name = field_name.split("(")[0]
                field_name = field_name.strip()
                field_expr = field_expr.strip()
                if field_name and field_name in self.numeric_field_list and field_expr:
                    if not self.is_number(field_expr):
                        self.check_result.error = _("该字段{field_name}为数值类型").format(field_name=field_name)
                        self.check_result.suggestion = _("请确认值的类型")
                        self.check_result.fixable = False
                        return False

        return True


class LuceneUnexpectedLogicOperatorChecker(LuceneCheckerBase):
    """
    检查是否存在意外的逻辑运算符
    """

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        super().__init__(query_string=query_string, fields=fields, force_check=True)

    def _check(self):
        query_string = self.query_string.strip()
        # 不能以 AND, OR, NOT 结尾
        query_string_word_list = query_string.split(" ")
        if len(query_string_word_list) < 2:
            return True
        if query_string_word_list[-1] in LuceneReservedLogicOperatorEnum.get_keys():
            self.check_result.error = _("多余的逻辑运算符{_logic_operator}").format(_logic_operator=query_string_word_list[-1])
            return False
        if query_string_word_list[0] in [
            LuceneReservedLogicOperatorEnum.AND.value,
            LuceneReservedLogicOperatorEnum.OR.value,
        ]:
            self.check_result.error = _("多余的逻辑运算符{_logic_operator}").format(_logic_operator=query_string_word_list[0])
            return False

        return True

    def _fix(self) -> str:
        query_string = self.query_string.strip()
        # 不能以 AND, OR, NOT 结尾
        query_string_word_list = query_string.split(" ")
        if len(query_string_word_list) < 2:
            return query_string
        if query_string_word_list[-1] in LuceneReservedLogicOperatorEnum.get_keys():
            return query_string[: -len(query_string_word_list[-1])].strip()
        if query_string_word_list[0] in [
            LuceneReservedLogicOperatorEnum.AND.value,
            LuceneReservedLogicOperatorEnum.OR.value,
        ]:
            return query_string[len(query_string_word_list[0]) :].strip()
        return query_string


class LuceneChecker(object):
    """
    Lucene语法检查器
    依次检查是否满足需要兼容的语法类型, 并转换成lucene支持的语法
    REGISTERED_CHECKERS中的顺序决定了检查的顺序
    """

    REGISTERED_CHECKERS = LuceneCheckerBase.__subclasses__()

    def __init__(self, query_string: str, fields: List[Dict[str, Any]] = None):
        # 原始的query_string, 用于日志记录, 前端回显
        self.origin_query_string: str = query_string
        self.query_string: str = query_string
        self.fields: List[Dict[str, Any]] = fields or []
        self.messages: List[str] = []

    def inspect(self):
        messages: List[str] = []
        for checker_class in self.REGISTERED_CHECKERS:
            checker = checker_class(query_string=self.query_string, fields=self.fields)
            checker.check()
            if not checker.check_result.legal:
                if checker.check_result.fixable:
                    checker.fix()
                    if checker.check_result.fixed:
                        self.query_string = checker.check_result.fixed_query_string
                messages.append(str(checker.check_result.error))
        if not messages:
            return True
        self.messages.extend(messages)
        return False

    def resolve(self):
        is_legal = True
        is_resolved = False
        for __ in range(MAX_RESOLVE_TIMES):
            if self.inspect():
                is_resolved = True
                break
        if self.messages:
            is_legal = False
        self.messages = ",".join(sorted(list(set(self.messages))))
        return {
            "is_legal": is_legal,
            "is_resolved": is_resolved,
            "message": self.messages,
            "keyword": self.query_string,
        }
