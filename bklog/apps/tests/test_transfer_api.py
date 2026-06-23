from django.test import SimpleTestCase

from apps.api.modules.transfer import parse_cluster_info


class ParseClusterInfoTest(SimpleTestCase):
    def _parse_custom_option(self, custom_option):
        cluster_obj = {
            "cluster_config": {"custom_option": custom_option},
            "auth_info": None,
        }

        return parse_cluster_info(cluster_obj)["cluster_config"]["custom_option"]

    def test_custom_option_missing_bk_biz_id_defaults_to_empty_string(self):
        for custom_option in ("{}", '{"visible_config": {"1": true}}'):
            with self.subTest(custom_option=custom_option):
                parsed_custom_option = self._parse_custom_option(custom_option)

                self.assertEqual(parsed_custom_option["bk_biz_id"], "")

    def test_empty_custom_option_defaults_to_empty_bk_biz_id(self):
        parsed_custom_option = self._parse_custom_option("")

        self.assertEqual(parsed_custom_option, {"bk_biz_id": ""})

    def test_invalid_or_non_dict_custom_option_defaults_to_empty_bk_biz_id(self):
        for custom_option in ("not-json", "[]"):
            with self.subTest(custom_option=custom_option):
                parsed_custom_option = self._parse_custom_option(custom_option)

                self.assertEqual(parsed_custom_option, {"bk_biz_id": ""})

    def test_custom_option_numeric_bk_biz_id_is_converted_to_int(self):
        parsed_custom_option = self._parse_custom_option('{"bk_biz_id": "123"}')

        self.assertEqual(parsed_custom_option["bk_biz_id"], 123)

    def test_custom_option_negative_bk_biz_id_is_converted_to_int(self):
        parsed_custom_option = self._parse_custom_option('{"bk_biz_id": "-123"}')

        self.assertEqual(parsed_custom_option["bk_biz_id"], -123)
