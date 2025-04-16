# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from django.conf.urls import include
from django.urls import re_path
from rest_framework import routers

from apps.log_search.views import (
    aggs_views,
    alert_strategy_view,
    bizs_views,
    favorite_search_views,
    field_views,
    index_set_views,
    meta_views,
    result_table_views,
    search_views,
    user_custom_config_views,
)

app_name = "apps.log_search"  # pylint: disable=invalid-name

router = routers.DefaultRouter(trailing_slash=True)

router.register(r"meta/language", meta_views.LanguageViewSet, basename="language")
router.register(r"meta/menu", meta_views.MenuViewSet, basename="menu")
router.register(r"meta", meta_views.MetaViewSet, basename="meta")

router.register(r"bizs", bizs_views.BizsViewSet, basename="bizs")

router.register(r"index_set", index_set_views.IndexSetViewSet, basename="index_set")

router.register(r"user_custom_config", user_custom_config_views.UserCustomConfigViewSet, basename="user_custom_config")

router.register(r"search/index_set", search_views.SearchViewSet, basename="search")
router.register(r"search/index_set", aggs_views.AggsViewSet, basename="aggs")
router.register(r"search/favorite", favorite_search_views.FavoriteViewSet, basename="favorite")
router.register(r"search/favorite_group", favorite_search_views.FavoriteGroupViewSet, basename="favorite_group")
router.register(r"search/favorite_union", favorite_search_views.FavoriteUnionSearchViewSet, basename="favorite_union")

router.register(r"result_table", result_table_views.ResultTablesViewSet, basename="result_table")

router.register(r"field/index_set", field_views.FieldViewSet, basename="field")
router.register(r"alert_strategy", alert_strategy_view.AlertStrategyViewSet, basename="alert_strategy")

urlpatterns = [re_path(r"^", include(router.urls))]
