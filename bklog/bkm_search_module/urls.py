# -*- coding: utf-8 -*-
from django.conf.urls import include, url
from rest_framework import routers

from bkm_search_module.views import (
    SearchModuleIndexSetSettingsViewSet,
    SearchModuleIndexSetViewSet,
    SearchModuleUserSettingsViewSet,
)

router = routers.DefaultRouter(trailing_slash=True)

router.register(r"index_set", SearchModuleIndexSetViewSet, basename="index_set")
router.register(
    r"index_set/(?P<index_set_id>[0-9]*)/settings", SearchModuleIndexSetSettingsViewSet, basename="settings"
)
router.register(r"settings", SearchModuleUserSettingsViewSet, basename="settings")

urlpatterns = [url(r"^", include(router.urls))]
