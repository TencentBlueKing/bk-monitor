# -*- coding: utf-8 -*-
from django.conf.urls import include
from django.urls import re_path
from rest_framework import routers

from bkm_search_module.views import (
    SearchModuleIndexSetSettingsViewSet,
    SearchModuleIndexSetViewSet,
    SearchModuleUserSettingsViewSet,
)

router = routers.DefaultRouter(trailing_slash=True)

router.register(r"index_set", SearchModuleIndexSetViewSet, basename="index_set")
router.register(
    r"index_set/(?P<index_set_id>[0-9]*)/settings", SearchModuleIndexSetSettingsViewSet, basename="index_set_settings"
)
router.register(r"settings", SearchModuleUserSettingsViewSet, basename="settings")

urlpatterns = [re_path(r"^", include(router.urls))]
