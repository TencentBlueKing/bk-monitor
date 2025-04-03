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
from apps.log_search.exceptions import IndexSetCustomConfigNotExistException
from apps.log_search.models import IndexSetCustomConfig


class IndexSetCustomConfigHandler(object):
    def __init__(self, index_set_id: int = None):
        self.index_set_id = index_set_id
        self.data = None
        if index_set_id:
            try:
                self.data = IndexSetCustomConfig.objects.get(index_set_id=self.index_set_id)
            except IndexSetCustomConfig.DoesNotExist:
                raise IndexSetCustomConfigNotExistException()

    def create_config(self, index_set_id: int, custom_config: dict):
        self.data = IndexSetCustomConfig.objects.create(index_set_id=index_set_id, custom_config=custom_config)
        return {"index_set_id": self.data.index_set_id, "custom_config": self.data.custom_config}

    def update_config(self, custom_config: dict):
        self.data.custom_config = custom_config
        self.data.save()
        return {"index_set_id": self.data.index_set_id, "custom_config": self.data.custom_config}

    def get_config(self):
        return {"index_set_id": self.data.index_set_id, "custom_config": self.data.custom_config}

    def delete_config(self):
        self.data.delete()
