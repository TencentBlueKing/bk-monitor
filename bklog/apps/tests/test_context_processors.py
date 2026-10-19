"""日志接入与权限申请指引的配置与内外网契约。"""

from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.utils.context_processors import mysetting


INTERNAL_GUIDE_URL = "https://iwiki.example.test/pages/viewpage.action?pageId=123"
INTERNAL_PERMISSION_GUIDE_URL = "https://iwiki.example.test/pages/viewpage.action?pageId=456"
COMMUNITY_DOC_URL = "https://docs.example.test/"
COMMUNITY_GUIDE_PATH = "markdown/ZH/LogSearch/4.7/UserGuide/QuickStart/guideline_log.md"
COMMUNITY_PERMISSION_GUIDE_PATH = "markdown/ZH/LogSearch/4.7/UserGuide/QuickStart/perm.md"
COLLECTOR_GUIDE_URL = "https://collector.example.test/guide"


@override_settings(
    DEFAULT_HTTPS_HOST="",
    DEPLOY_MODE="",
    PAAS_API_HOST="https://paas.example.test",
    BK_PAAS_HOST="https://paas.example.test",
    EXTERNAL_PAAS_HOST="https://external.example.test",
    USE_APIGW=False,
    SITE_URL="/",
    STATIC_URL="/static/",
    HEADER_CONFIG={"en": "Log", "zh": "日志"},
    TITLE_MENU_CONFIG={"en": "Log", "zh": "日志"},
    MENU_LOGO_URL="logo.svg",
    BK_DOC_URL=COMMUNITY_DOC_URL,
    BK_LOG_ACCESS_GUIDE_URL=INTERNAL_GUIDE_URL,
    BK_LOG_PERMISSION_GUIDE_URL=INTERNAL_PERMISSION_GUIDE_URL,
    COLLECTOR_GUIDE_URL=COLLECTOR_GUIDE_URL,
)
class LogAccessGuideContextTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _context(self, is_external=None):
        headers = {} if is_external is None else {"HTTP_IS_EXTERNAL": is_external}
        request = self.factory.get("/", **headers)
        request.user = SimpleNamespace(is_superuser=False)
        return mysetting(request)

    def _assert_guide_urls(self, context, access_url, permission_url):
        self.assertEqual(context["BK_LOG_ACCESS_GUIDE_URL"], access_url)
        self.assertEqual(context["BK_LOG_PERMISSION_GUIDE_URL"], permission_url)

    def test_ordinary_requests_use_configured_guide_for_all_versions(self):
        for run_ver in ("tencent", "ee", "ce", "open"):
            for is_external in (None, "false"):
                with self.subTest(run_ver=run_ver, is_external=is_external), override_settings(RUN_VER=run_ver):
                    self._assert_guide_urls(
                        self._context(is_external), INTERNAL_GUIDE_URL, INTERNAL_PERMISSION_GUIDE_URL
                    )

    def test_external_requests_always_use_document_center_for_all_versions(self):
        for run_ver in ("tencent", "ee", "ce", "open"):
            for guide_url, permission_guide_url in (
                (INTERNAL_GUIDE_URL, INTERNAL_PERMISSION_GUIDE_URL),
                ("", ""),
            ):
                with (
                    self.subTest(run_ver=run_ver, guide_url=guide_url),
                    override_settings(
                        RUN_VER=run_ver,
                        BK_LOG_ACCESS_GUIDE_URL=guide_url,
                        BK_LOG_PERMISSION_GUIDE_URL=permission_guide_url,
                    ),
                ):
                    self._assert_guide_urls(
                        self._context("true"),
                        f"{COMMUNITY_DOC_URL}{COMMUNITY_GUIDE_PATH}",
                        f"{COMMUNITY_DOC_URL}{COMMUNITY_PERMISSION_GUIDE_PATH}",
                    )

    @override_settings(BK_LOG_ACCESS_GUIDE_URL="", BK_LOG_PERMISSION_GUIDE_URL="")
    def test_ordinary_requests_without_configuration_use_document_center_for_all_versions(self):
        for run_ver in ("tencent", "ee", "ce", "open"):
            for is_external in (None, "false"):
                with self.subTest(run_ver=run_ver, is_external=is_external), override_settings(RUN_VER=run_ver):
                    self._assert_guide_urls(
                        self._context(is_external),
                        f"{COMMUNITY_DOC_URL}{COMMUNITY_GUIDE_PATH}",
                        f"{COMMUNITY_DOC_URL}{COMMUNITY_PERMISSION_GUIDE_PATH}",
                    )

    def test_document_center_guide_handles_custom_and_missing_roots(self):
        roots = (
            (
                "https://custom.example.test/docs",
                f"https://custom.example.test/docs/{COMMUNITY_GUIDE_PATH}",
                f"https://custom.example.test/docs/{COMMUNITY_PERMISSION_GUIDE_PATH}",
            ),
            (
                "https://custom.example.test/docs/",
                f"https://custom.example.test/docs/{COMMUNITY_GUIDE_PATH}",
                f"https://custom.example.test/docs/{COMMUNITY_PERMISSION_GUIDE_PATH}",
            ),
            (
                "https://custom.example.test/docs///",
                f"https://custom.example.test/docs/{COMMUNITY_GUIDE_PATH}",
                f"https://custom.example.test/docs/{COMMUNITY_PERMISSION_GUIDE_PATH}",
            ),
            ("", "", ""),
            (None, "", ""),
        )
        for is_external, guide_url, permission_guide_url in (
            (None, "", ""),
            ("true", INTERNAL_GUIDE_URL, INTERNAL_PERMISSION_GUIDE_URL),
        ):
            for doc_url, expected_access, expected_permission in roots:
                with (
                    self.subTest(is_external=is_external, doc_url=doc_url),
                    override_settings(
                        BK_DOC_URL=doc_url,
                        BK_LOG_ACCESS_GUIDE_URL=guide_url,
                        BK_LOG_PERMISSION_GUIDE_URL=permission_guide_url,
                    ),
                ):
                    self._assert_guide_urls(self._context(is_external), expected_access, expected_permission)

    def test_configured_guide_does_not_require_document_center_root(self):
        for is_external in (None, "false"):
            for doc_url in ("", None):
                with self.subTest(is_external=is_external, doc_url=doc_url), override_settings(BK_DOC_URL=doc_url):
                    self._assert_guide_urls(
                        self._context(is_external), INTERNAL_GUIDE_URL, INTERNAL_PERMISSION_GUIDE_URL
                    )

    def test_access_and_permission_guides_use_independent_configuration(self):
        configurations = (
            (
                "",
                INTERNAL_PERMISSION_GUIDE_URL,
                f"{COMMUNITY_DOC_URL}{COMMUNITY_GUIDE_PATH}",
                INTERNAL_PERMISSION_GUIDE_URL,
            ),
            (
                INTERNAL_GUIDE_URL,
                "",
                INTERNAL_GUIDE_URL,
                f"{COMMUNITY_DOC_URL}{COMMUNITY_PERMISSION_GUIDE_PATH}",
            ),
        )
        for is_external in (None, "false"):
            for access_url, permission_url, expected_access, expected_permission in configurations:
                with (
                    self.subTest(is_external=is_external, access_url=access_url),
                    override_settings(BK_LOG_ACCESS_GUIDE_URL=access_url, BK_LOG_PERMISSION_GUIDE_URL=permission_url),
                ):
                    self._assert_guide_urls(self._context(is_external), expected_access, expected_permission)

    def test_existing_document_fields_are_unchanged(self):
        for run_ver in ("tencent", "ee"):
            for is_external in (None, "false", "true"):
                with self.subTest(run_ver=run_ver, is_external=is_external), override_settings(RUN_VER=run_ver):
                    context = self._context(is_external)
                    self.assertEqual(context["BK_DOC_URL"], COMMUNITY_DOC_URL)
                    self.assertEqual(context["COLLECTOR_GUIDE_URL"], COLLECTOR_GUIDE_URL)
                    self.assertEqual(context["IS_EXTERNAL"], "false" if is_external is None else is_external)
