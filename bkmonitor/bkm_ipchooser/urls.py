# -*- coding: utf-8 -*-
from rest_framework.routers import DefaultRouter

from bkm_ipchooser.views import (
    IpChooserConfigViewSet,
    IpChooserDynamicGroupViewSet,
    IpChooserHostViewSet,
    IpChooserServiceInstanceViewSet,
    IpChooserTemplateViewSet,
    IpChooserTopoViewSet,
)

routers = DefaultRouter(trailing_slash=True)

routers.register("topo", IpChooserTopoViewSet, basename="ipchooser_topo")
routers.register("host", IpChooserHostViewSet, basename="ipchooser_host")
routers.register("service_instance", IpChooserServiceInstanceViewSet, basename="ipchooser_service_instance")
routers.register("template", IpChooserTemplateViewSet, basename="ipchooser_template")
routers.register("config", IpChooserConfigViewSet, basename="ipchooser_config")
routers.register("dynamic_group", IpChooserDynamicGroupViewSet, basename="ipchooser_dynamic_group")

urlpatterns = routers.urls
