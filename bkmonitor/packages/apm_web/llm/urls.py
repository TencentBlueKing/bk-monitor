from django.urls import include, re_path

from apm_web.llm import views
from core.drf_resource.routers import ResourceRouter

router = ResourceRouter()
router.trailing_slash = "/?"
router.register(r"", views.LLMViewSet, basename="llm")

urlpatterns = [
    re_path(r"^", include(router.urls)),
]
