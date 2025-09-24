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

from apps.generic import APIViewSet
from apps.log_search.handlers.index_group import IndexGroupHandler
from rest_framework.response import Response

from apps.log_search.serializers import IndexGroupListSerializer, CreateIndexGroupSerializer, UpdateIndexGroupSerializer


class IndexGroupViewSet(APIViewSet):
    """
    索引组（新的索引集概念）
    """

    lookup_field = "index_set_id"

    def list(self, request, *args, **kwargs):
        """
        @api {get} /index_group/ 索引组列表
        @apiName list_index_group
        @apiGroup index_group
        @apiParam {String} space_uid 空间唯一标识
        @apiParam {String} keyword 关键字
        @apiSuccess {Int} data.index_set_id 索引组id
        @apiSuccess {Int} data.index_set_name 索引组名称
        @apiSuccess {Int} data.index_count 索引数量
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [{
                "index_set_id": 899,
                "index_set_name": "first_group",
                "index_count": 3
            }],
            "result": true
        }
        """
        params = self.params_valid(IndexGroupListSerializer)
        return Response(IndexGroupHandler.list_index_groups(params))

    def create(self, request, *args, **kwargs):
        """
        @api {post} /index_group/ 创建索引组
        @apiName create_index_group
        @apiGroup index_group
        @apiParam {String} space_uid 空间唯一标识
        @apiParam {String} index_set_name 索引组名称
        @apiSuccess {Int} data.index_set_id 索引组id
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "index_set_id": 899
            },
            "result": true
        }
        """
        params = self.params_valid(CreateIndexGroupSerializer)
        index_group = IndexGroupHandler.create_index_groups(params)
        return Response({"index_set_id": index_group.index_set_id})

    def update(self, request, index_set_id):
        """
        @api {put} /index_group/$index_set_id 更新索引组（目前只能修改名称）
        @apiName update_index_group
        @apiGroup index_group
        @apiParam {String} index_set_name 索引组名称
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        params = self.params_valid(UpdateIndexGroupSerializer)
        IndexGroupHandler(index_set_id).update_index_groups(params)
        return Response()

    def destroy(self, request, index_set_id):
        """
        @api {delete} /index_group/$index_set_id 删除索引组
        @apiName delete_index_group
        @apiGroup index_group
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        IndexGroupHandler(index_set_id).delete_index_groups()
        return Response()
