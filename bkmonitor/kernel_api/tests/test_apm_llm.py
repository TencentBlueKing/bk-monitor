import importlib.util
from pathlib import Path

import pytest
from django.test import override_settings
from django.urls import Resolver404, include, re_path, resolve

from core.drf_resource.routers import ResourceRouter


def load_apm_v4_views():
    module_path = Path(__file__).resolve().parents[1] / "views" / "v4" / "apm.py"
    spec = importlib.util.spec_from_file_location("kernel_api_v4_apm_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


apm_v4_views = load_apm_v4_views()
router = ResourceRouter()
router.register_module(apm_v4_views)

# Only register the APM V4 module under test. Using kernel_api.urls would import
# every V2/V4 view module and make this route test depend on unrelated settings.
urlpatterns = [
    re_path(r"^api/v4/", include((router.urls, "kernel_api"), namespace="api.v4")),
]


@pytest.mark.filterwarnings("ignore:CoreAPI compatibility is deprecated.*")
@override_settings(ROOT_URLCONF=__name__)
def test_apm_llm_v4_routes_exist():
    for endpoint in ("list_spans", "list_traces", "list_flows", "time_series", "calculate_by_range"):
        match = resolve(f"/api/v4/apm_llm_web/{endpoint}/")

        assert match.func.cls is apm_v4_views.ApmLLMWebViewSet


@pytest.mark.filterwarnings("ignore:CoreAPI compatibility is deprecated.*")
@override_settings(ROOT_URLCONF=__name__)
def test_llm_base_v4_routes_do_not_exist():
    for endpoint in ("list_spans", "list_traces", "list_flows", "time_series", "calculate_by_range"):
        with pytest.raises(Resolver404):
            resolve(f"/api/v4/llm/{endpoint}/")
