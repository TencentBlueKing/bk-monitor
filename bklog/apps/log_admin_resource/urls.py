from django.conf.urls import include
from django.urls import re_path
from rest_framework import routers

from apps.log_admin_resource.views import AdminResourceViewSet


router = routers.DefaultRouter(trailing_slash=True)
router.register(r"admin/resource", AdminResourceViewSet, basename="admin_resource")

urlpatterns = [re_path(r"^", include(router.urls))]
