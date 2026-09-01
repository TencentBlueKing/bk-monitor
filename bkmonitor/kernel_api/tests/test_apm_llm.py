import pytest
from django.test import override_settings
from django.urls import resolve

from kernel_api.views.v4.apm import ApmLLMWebViewSet


@pytest.mark.filterwarnings("ignore:CoreAPI compatibility is deprecated.*")
@override_settings(ROOT_URLCONF="kernel_api.urls")
def test_apm_llm_v4_routes_exist():
    for endpoint in ("list_spans", "list_traces"):
        match = resolve(f"/api/v4/apm_llm_web/{endpoint}/")

        assert match.func.cls is ApmLLMWebViewSet
