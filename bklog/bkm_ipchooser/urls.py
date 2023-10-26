# -*- coding: utf-8 -*-
from bkm_ipchooser.views import (
    IpChooserConfigViewSet,
    IpChooserDynamicGroupViewSet,
    IpChooserHostViewSet,
    IpChooserTemplateViewSet,
    IpChooserTopoViewSet,
)
from rest_framework.routers import DefaultRouter

routers = DefaultRouter(trailing_slash=True)

routers.register("topo", IpChooserTopoViewSet, basename="ipchooser_topo")
routers.register("host", IpChooserHostViewSet, basename="ipchooser_host")
routers.register("template", IpChooserTemplateViewSet, basename="ipchooser_template")
routers.register("config", IpChooserConfigViewSet, basename="ipchooser_config")
routers.register("dynamic_group", IpChooserDynamicGroupViewSet, basename="ipchooser_dynamic_group")

urlpatterns = routers.urls
