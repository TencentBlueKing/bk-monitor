from core.drf_resource import routers
from local_app.views import TestViewSet

router = routers.DefaultRouter()
router.register("", TestViewSet, basename="test")

urlpatterns = router.urls
