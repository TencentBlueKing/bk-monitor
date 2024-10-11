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
from apps.log_clustering.models import ClusteringTemplate


class ClusteringTemplateHandler(object):
    def __init__(self, space_uid: str):
        self.space_uid = space_uid

    def get_template(self):
        data = ClusteringTemplate.objects.filter(space_uid=self.space_uid).values(
            "id", "space_uid", "template_name", "predefined_varibles"
        )
        # 空间存在模板
        if data.exists():
            return list(data)
        # TODO:不存在模板，后台获取系统默认的正则规则，创建模板并返回

    def create_template(self, template_name, predefined_varibles):
        instance = ClusteringTemplate.objects.create(
            space_uid=self.space_uid, template_name=template_name, predefined_varibles=predefined_varibles
        )
        return {
            "id": instance.id,
            "space_uid": instance.space_uid,
            "template_name": instance.template_name,
            "predefined_varibles": instance.predefined_varibles,
        }
