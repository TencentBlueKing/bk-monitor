"""
V4 清洗 doris_storage_config / es_storage_config 生成测试

重点覆盖 JSON 容器字段的识别：object / flattened 的 output_type 是 dict，
nested 的 output_type 是 nested，两者都必须进 Doris 的 json_fields。
"""

from unittest import TestCase

from apps.log_databus.constants import DORIS_CLUSTER_TYPE, STORAGE_CLUSTER_TYPE
from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_text import BkLogTextEtlStorage
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import make_field

ES_TYPE_BY_FIELD_TYPE = {
    "string": "keyword",
    "int": "integer",
    "double": "double",
    "object": "object",
    "flattened": "flattened",
    "nested": "nested",
}


def with_es_type(field):
    """补齐 option.es_type，模拟 get_result_table_fields 产出的 field_list 元素"""
    field = dict(field, option=dict(field.get("option") or {}))
    field["option"].setdefault("es_type", ES_TYPE_BY_FIELD_TYPE.get(field["field_type"], "keyword"))
    return field


def build_field_list(fields, built_in_config):
    """构造带 es_type 的 field_list（doris 分支会读 option.es_type）"""
    field_list = [with_es_type(field) for field in built_in_config.get("fields", [])]
    field_list += [with_es_type(field) for field in fields]
    if "time_field" in built_in_config:
        field_list.append(built_in_config["time_field"])
    return field_list


def build_doris_config(storage, fields, etl_params):
    config = get_fresh_config()
    result = storage.build_log_v4_data_link(
        fields,
        etl_params,
        config,
        build_field_list(fields, config),
        storage_cluster_type=DORIS_CLUSTER_TYPE,
    )
    return result


class TestDorisJsonFields(TestCase):
    """Doris json_fields 必须覆盖 object / flattened / nested 三种容器类型"""

    def test_regexp_json_container_fields(self):
        """正则：object / flattened / nested 都要进 json_fields，标量字段不进"""
        etl_params = {
            "separator_regexp": r"(?P<meta>\S+)\s+(?P<attrs>\S+)\s+(?P<events>\S+)\s+(?P<level>\w+)",
            "retain_original_text": False,
        }
        fields = [
            make_field("meta", "object"),
            make_field("attrs", "flattened"),
            make_field("events", "nested"),
            make_field("level", "string"),
        ]
        result = build_doris_config(BkLogRegexpEtlStorage(), fields, etl_params)
        json_fields = result["doris_storage_config"]["json_fields"]

        self.assertIn("meta", json_fields)
        self.assertIn("attrs", json_fields)
        self.assertIn("events", json_fields)
        self.assertNotIn("level", json_fields)

    def test_delimiter_json_container_fields(self):
        """分隔符：按 field_index 提取的容器字段同样要进 json_fields"""
        etl_params = {"separator": "|", "retain_original_text": False}
        fields = [
            make_field("meta", "object", field_index=1),
            make_field("attrs", "flattened", field_index=2),
            make_field("events", "nested", field_index=3),
            make_field("level", "string", field_index=4),
        ]
        result = build_doris_config(BkLogDelimiterEtlStorage(), fields, etl_params)
        json_fields = result["doris_storage_config"]["json_fields"]

        self.assertIn("meta", json_fields)
        self.assertIn("attrs", json_fields)
        self.assertIn("events", json_fields)
        self.assertNotIn("level", json_fields)

    def test_json_etl_nested_field(self):
        """JSON 清洗：nested 字段同样不能被漏掉"""
        etl_params = {"retain_original_text": False}
        fields = [make_field("events", "nested"), make_field("level", "string")]
        result = build_doris_config(BkLogJsonEtlStorage(), fields, etl_params)
        json_fields = result["doris_storage_config"]["json_fields"]

        self.assertIn("events", json_fields)
        self.assertNotIn("level", json_fields)

    def test_built_in_ext_field_is_json_field(self):
        """内置 __ext 是 es_type=object，直接 assign(dict)，仍应被识别为 JSON 字段"""
        result = build_doris_config(BkLogTextEtlStorage(), [], {})
        self.assertIn("__ext", result["doris_storage_config"]["json_fields"])

    def test_json_fields_sorted(self):
        """json_fields 与 search_zh 需排序输出，避免集合迭代顺序导致配置无意义变更"""
        etl_params = {
            "separator_regexp": r"(?P<zeta>\S+)\s+(?P<alpha>\S+)\s+(?P<msg>.+)",
            "retain_original_text": False,
        }
        fields = [
            make_field("zeta", "object"),
            make_field("alpha", "nested"),
            make_field("msg", "string"),
        ]
        fields[2]["is_analyzed"] = True
        fields[2]["option"] = {"es_type": "text"}
        result = build_doris_config(BkLogRegexpEtlStorage(), fields, etl_params)
        doris_config = result["doris_storage_config"]

        self.assertEqual(doris_config["json_fields"], sorted(doris_config["json_fields"]))
        search_zh = doris_config["field_config_group"]["search_zh"]
        self.assertEqual(search_zh, sorted(search_zh))
        self.assertIn("msg", search_zh)


class TestFieldWithoutEsType(TestCase):
    """聚类场景（etl_flat）字段原样透传，option 里没有 es_type"""

    def test_field_list_without_es_type(self):
        """缺少 es_type 的字段应被跳过，而不是抛 KeyError"""
        config = get_fresh_config()
        fields = [make_field("meta", "object"), make_field("msg", "string")]
        field_list = build_field_list(fields, config)
        # 模拟 get_result_table_fields 中 etl_flat 分支直接 append 原始字段的形态
        field_list.append({"field_name": "__dist_05", "field_type": "string", "option": {}})
        field_list.append({"field_name": "__dist_09", "field_type": "string"})

        result = BkLogRegexpEtlStorage().build_log_v4_data_link(
            fields,
            {"separator_regexp": r"(?P<meta>\S+)\s+(?P<msg>.+)", "retain_original_text": False},
            config,
            field_list,
            storage_cluster_type=DORIS_CLUSTER_TYPE,
        )

        search_zh = result["doris_storage_config"]["field_config_group"]["search_zh"]
        self.assertNotIn("__dist_05", search_zh)
        self.assertNotIn("__dist_09", search_zh)


class TestStorageConfigBranch(TestCase):
    """ES 与 Doris 存储配置互斥输出"""

    def test_es_storage_config_only(self):
        """ES 集群只产出 es_storage_config，且不塞入 doris 配置"""
        config = get_fresh_config()
        fields = [make_field("meta", "object")]
        result = BkLogRegexpEtlStorage().build_log_v4_data_link(
            fields,
            {"separator_regexp": r"(?P<meta>.+)", "retain_original_text": False},
            config,
            build_field_list(fields, config),
            storage_cluster_type=STORAGE_CLUSTER_TYPE,
        )

        self.assertEqual(
            result["es_storage_config"],
            {"unique_field_list": config["option"]["es_unique_field_list"], "timezone": 8},
        )
        self.assertNotIn("doris_storage_config", result)

    def test_doris_storage_config_only(self):
        """Doris 集群只产出 doris_storage_config"""
        etl_params = {"separator_regexp": r"(?P<meta>.+)", "retain_original_text": False}
        result = build_doris_config(BkLogRegexpEtlStorage(), [make_field("meta", "object")], etl_params)

        self.assertNotIn("es_storage_config", result)
        self.assertEqual(
            result["doris_storage_config"]["storage_keys"],
            get_fresh_config()["option"]["es_unique_field_list"],
        )
