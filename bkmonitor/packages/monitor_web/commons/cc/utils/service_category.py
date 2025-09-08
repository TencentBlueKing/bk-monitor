# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from core.drf_resource import api


class ServiceCategorySearcher(object):
    def __init__(self):
        # 用于存储服务分类数据，避免多次调用cmdb接口
        self._service_category_data = {}

    def get_biz_service_category_data(self, bk_biz_id):
        if not self._service_category_data.get(bk_biz_id):
            # 获取业务下的服务分类
            res_service_category = api.cmdb.search_service_category(bk_biz_id=bk_biz_id)
            biz_service_category_mapping = self._service_category_data.setdefault(bk_biz_id, {})
            for cate in res_service_category:
                category_id = cate["id"]
                biz_service_category_mapping[category_id] = cate

        return self._service_category_data[bk_biz_id]

    def search(self, bk_biz_id, category_id):
        category_mapping = self.get_biz_service_category_data(bk_biz_id)
        category_info = category_mapping.get(category_id)
        if not category_info:
            return None
        label = {"first": "", "second": ""}
        if category_info.get("bk_parent_id"):
            parent_info = category_mapping.get(category_info["bk_parent_id"], {})
            label["first"] = parent_info.get("name", "")
            label["second"] = category_info.get("name", "")
        else:
            label["first"] = category_info.get("name", "")

        return label
