from unittest import skipUnless
from unittest.mock import patch

from django.apps import apps
from django.db import models
from django.test import SimpleTestCase, TestCase

from apps.log_search.constants import UserMetaConfType
from apps.log_search.handlers.meta import MetaHandler
from apps.log_search.models import IndexSetFieldsConfig, UserIndexSetFieldsConfig, UserMetaConf

REPORTED_USERNAME = "menglihong.janaa_shengqugames@tai"
LONG_USERNAME = "u" * 60 + "@tai"
SAME_PREFIX_USERNAME = "u" * 32 + "v" * 28 + "@tai"


class UsernameFieldValidationTest(SimpleTestCase):
    def test_user_identity_fields_accept_long_usernames(self):
        identity_fields = {"created_by", "updated_by", "deleted_by", "username"}
        checked_fields = []

        for app_config in apps.get_app_configs():
            if not app_config.name.startswith("apps."):
                continue
            for model in app_config.get_models():
                for field in model._meta.get_fields():
                    if field.name not in identity_fields or not isinstance(field, models.CharField):
                        continue
                    checked_fields.append(f"{model._meta.label}.{field.name}")
                    for username in (REPORTED_USERNAME, LONG_USERNAME):
                        with self.subTest(model=model._meta.label, field=field.name, username_length=len(username)):
                            self.assertEqual(field.clean(username, None), username)

        self.assertTrue(checked_fields)


class LongUsernameUserGuideTest(TestCase):
    def test_repeated_get_preserves_user_function_guide(self):
        result = MetaHandler.get_user_guide(LONG_USERNAME)
        self.assertTrue(result["function_guide"]["search_favorite"])

        MetaHandler.update_user_guide(LONG_USERNAME, {"function_guide": "search_favorite"})
        result = MetaHandler.get_user_guide(LONG_USERNAME)

        self.assertFalse(result["function_guide"]["search_favorite"])
        guides = UserMetaConf.objects.filter(username=LONG_USERNAME, type=UserMetaConfType.FUNCTION_GUIDE)
        self.assertEqual(guides.count(), 1)
        self.assertEqual(guides.get().username, LONG_USERNAME)

    def test_users_with_same_first_32_characters_have_separate_guides(self):
        MetaHandler.get_user_guide(LONG_USERNAME)
        MetaHandler.get_user_guide(SAME_PREFIX_USERNAME)

        MetaHandler.update_user_guide(LONG_USERNAME, {"function_guide": "search_favorite"})

        self.assertFalse(MetaHandler.get_user_guide(LONG_USERNAME)["function_guide"]["search_favorite"])
        self.assertTrue(MetaHandler.get_user_guide(SAME_PREFIX_USERNAME)["function_guide"]["search_favorite"])
        usernames = UserMetaConf.objects.filter(type=UserMetaConfType.FUNCTION_GUIDE).values_list("username", flat=True)
        self.assertCountEqual(usernames, [LONG_USERNAME, SAME_PREFIX_USERNAME])


class LongUsernameVersionLogTest(TestCase):
    @skipUnless(apps.is_installed("version_log"), "版本日志应用未启用")
    def test_repeated_visit_updates_same_user(self):
        version_log_visited = apps.get_model("version_log", "VersionLogVisited")
        username_field = version_log_visited._meta.get_field("username")
        self.assertEqual(username_field.clean(LONG_USERNAME, None), LONG_USERNAME)

        version_log_visited.objects.update_visit_version(LONG_USERNAME, "1.0.0")
        version_log_visited.objects.update_visit_version(LONG_USERNAME, "1.1.0")

        self.assertEqual(version_log_visited.objects.count(), 1)
        visit = version_log_visited.objects.get(username=LONG_USERNAME)
        self.assertEqual(visit.username, LONG_USERNAME)
        self.assertEqual(visit.visited_version, "1.1.0")


class LongUsernameIndexSetFieldsTest(TestCase):
    @patch("apps.log_search.models.get_request_app_code", return_value="bklog")
    def test_personal_field_configuration_uses_full_username(self, _get_app_code):
        config = IndexSetFieldsConfig.objects.create(
            name="custom", index_set_id=1, display_fields=["log"], source_app_code="bklog"
        )
        UserIndexSetFieldsConfig.objects.create(
            index_set_id=1, config_id=config.pk, username=LONG_USERNAME, source_app_code="bklog"
        )

        self.assertEqual(UserIndexSetFieldsConfig.get_config(index_set_id=1, username=LONG_USERNAME), config)
        self.assertIsNone(UserIndexSetFieldsConfig.get_config(index_set_id=1, username=SAME_PREFIX_USERNAME))
